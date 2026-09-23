#!/usr/bin/env python3
"""Reproducible, privacy-safe UX/performance baseline for the local web UI.

This developer check creates synthetic skills in a temporary directory, starts
the existing loopback server, and records bounded REST timings. It never reads
the user's normal data directory and never sends telemetry. The fixture plan
is deliberately small enough to run in CI while including the large-library
shape that drives the product plan.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from math import ceil
from pathlib import Path
from statistics import median
from threading import Thread
from urllib.request import urlopen

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer

try:
    import resource
except ImportError:  # pragma: no cover - resource is not available on Windows
    resource = None


FIXTURE_PLAN = {
    "empty": {
        "description": "Initialized store with no skill documents.",
        "skill_count": 0,
        "expected_states": ["empty"],
    },
    "small": {
        "description": "Twelve ordinary active skills with stable descriptions.",
        "skill_count": 12,
        "expected_states": ["active"],
    },
    "divergent": {
        "description": "Identical and divergent same-name copies across agent roots.",
        "skill_count": 4,
        "expected_states": ["duplicated", "divergent"],
    },
    "malformed": {
        "description": "One valid document and one malformed frontmatter document.",
        "skill_count": 2,
        "expected_states": ["active", "malformed"],
    },
    "large": {
        "description": "Two thousand deterministic active documents.",
        "skill_count": 2000,
        "expected_states": ["active"],
    },
}

FULL_INVENTORY_SIZES = (100, 1000, 10000)
FULL_INVENTORY_SAMPLES = 20
FULL_INVENTORY_ROUTES = {
    "scopes": "/api/scopes",
    "merged_list": "/api/skills?scope=all",
    "stats": "/api/stats?scope=all",
    "doctor": "/api/doctor?scope=all",
    "hygiene": "/api/doctor?scope=all&hygiene=1",
}
MAX_INVENTORY_SKILLS = 10000
MAX_INVENTORY_FILE_BYTES = 512
MAX_INVENTORY_TOTAL_BYTES = 8 * 1024 * 1024
INVENTORY_REQUEST_TIMEOUT_S = 60
INVENTORY_RUNTIME_LIMIT_S = 900
MIN_P95_SAMPLES = 20


def fixture_plan() -> dict[str, dict]:
    """Return a copy of the public fixture contract for tests and tooling."""
    return {name: dict(spec) for name, spec in FIXTURE_PLAN.items()}


def _write_skill(root: Path, name: str, description: str, body: str = "") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "category: baseline\n"
        "---\n\n"
        f"{body or 'Deterministic baseline fixture content.'}\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _write_inventory_skill(root: Path, index: int) -> int:
    """Write one bounded inventory document and return its encoded byte size."""
    name = f"inventory-skill-{index:05d}"
    content = (
        "---\n"
        f"name: {name}\n"
        "description: Deterministic full-inventory benchmark fixture.\n"
        "category: baseline\n"
        "---\n\n"
        "Synthetic benchmark content; no user data.\n"
    )
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_INVENTORY_FILE_BYTES:
        raise ValueError("inventory fixture document exceeds its byte limit")
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(encoded)
    return len(encoded)


def _nearest_rank(samples: list[float], percentile: float) -> float | None:
    """Return the nearest-rank percentile, where rank is ceil(p * n)."""
    if not samples:
        return None
    rank = max(1, ceil(percentile * len(samples)))
    return round(sorted(samples)[rank - 1], 2)


def summarize_samples(samples: list[float]) -> dict:
    """Return reproducible median and nearest-rank p95 summary data."""
    return {
        "sample_count": len(samples),
        "samples_ms": [round(value, 2) for value in samples],
        "median_ms": round(median(samples), 2) if samples else None,
        "p95_ms_nearest_rank": _nearest_rank(samples, 0.95),
    }


def _inventory_store(data_dir: Path) -> Store:
    """Create a fresh Store wrapper around the already indexed fixture tree."""
    store = Store(data_dir=data_dir)
    store.init_db()
    return store


def _inventory_server(store: Store) -> tuple[WebAppServer, Thread]:
    """Start a fresh loopback server with a short shutdown poll interval."""
    server = WebAppServer(store, port=0)
    thread = Thread(
        target=server.httpd.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    return server, thread


def _close_inventory_server(server: WebAppServer, thread: Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)


def _inventory_count(route: str, payload: dict | list) -> int | None:
    """Extract a count exposed by a route without retaining raw path data."""
    if route == "merged_list" and isinstance(payload, list):
        return len(payload)
    if route == "stats" and isinstance(payload, dict):
        return payload.get("all_total")
    if route == "hygiene" and isinstance(payload, dict):
        summary = (payload.get("hygiene") or {}).get("summary") or {}
        return summary.get("physical_instances")
    if route == "scopes" and isinstance(payload, list):
        global_scope = next((item for item in payload if item.get("id") == "global"), {})
        return global_scope.get("count")
    return None


def _inventory_degraded_count(route: str, payload: dict | list) -> int:
    if route == "hygiene" and isinstance(payload, dict):
        return len((payload.get("hygiene") or {}).get("degraded") or [])
    if route == "doctor" and isinstance(payload, dict):
        return len(payload.get("degraded") or [])
    return 0


def _measure_inventory_request(
    data_dir: Path,
    route_name: str,
    route_path: str,
    timeout_s: int,
    *,
    server_pair: tuple[WebAppServer, Thread] | None = None,
    deadline: float | None = None,
) -> dict:
    """Measure one request, optionally reusing the warm server and Store."""
    owns_server = server_pair is None
    if server_pair is None:
        server_pair = _inventory_server(_inventory_store(data_dir))
    server, thread = server_pair
    try:
        if deadline is not None and deadline - time.perf_counter() < timeout_s:
            return {"status": "not_run", "reason": "insufficient runtime budget for request timeout"}
        payload, elapsed_ms = _get_json(server.url + route_path, timeout=timeout_s)
        return {
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "observed_count": _inventory_count(route_name, payload),
            "degraded_sections": _inventory_degraded_count(route_name, payload),
            "response_keys": sorted(payload) if isinstance(payload, dict) else None,
        }
    except Exception as exc:
        return {"status": "timeout" if isinstance(exc, TimeoutError) else "error",
                "error_type": type(exc).__name__}
    finally:
        if owns_server:
            _close_inventory_server(server, thread)


def _build_inventory_fixture(size: int, workspace: Path) -> tuple[Store, dict]:
    if size not in FULL_INVENTORY_SIZES or size > MAX_INVENTORY_SKILLS:
        raise ValueError(f"unsupported full-inventory size: {size}")
    store = Store(data_dir=workspace / "data")
    store.init_db()
    fixture_started = time.perf_counter()
    bytes_written = 0
    for index in range(size):
        bytes_written += _write_inventory_skill(store.skills_dir, index)
        if bytes_written > MAX_INVENTORY_TOTAL_BYTES:
            raise ValueError("inventory fixture exceeds its total byte limit")
    fixture_write_ms = round((time.perf_counter() - fixture_started) * 1000, 2)
    observed_files = sum(1 for entry in store.skills_dir.iterdir() if (entry / "SKILL.md").is_file())
    if observed_files != size:
        raise RuntimeError(f"fixture count mismatch: expected {size}, found {observed_files}")
    resync_started = time.perf_counter()
    store.resync()
    resync_ms = round((time.perf_counter() - resync_started) * 1000, 2)
    return store, {
        "expected_skill_count": size,
        "created_skill_count": observed_files,
        "fixture_bytes": bytes_written,
        "fixture_write_ms": fixture_write_ms,
        "index_resync_ms": resync_ms,
    }


def _empty_inventory_sample(sample_number: int, reason: str) -> dict:
    return {"sample": sample_number, "status": "not_run", "reason": reason}


def _sample_inventory_routes(
    data_dir: Path,
    size: int,
    samples: int,
    timeout_s: int,
    deadline: float,
) -> tuple[dict, dict]:
    cold = {}
    warm = {}
    for route_name, route_path in FULL_INVENTORY_ROUTES.items():
        cold_rows = []
        for sample_number in range(1, samples + 1):
            if deadline - time.perf_counter() < timeout_s:
                cold_rows.append(_empty_inventory_sample(sample_number, "insufficient runtime budget for request timeout"))
                continue
            row = _measure_inventory_request(data_dir, route_name, route_path, timeout_s, deadline=deadline)
            row["sample"] = sample_number
            cold_rows.append(row)
            if row.get("observed_count") not in (None, size):
                row["status"] = "count_mismatch"
                row["expected_count"] = size
        cold[route_name] = _summarize_inventory_rows(cold_rows)
    for route_name, route_path in FULL_INVENTORY_ROUTES.items():
        warm_rows = []
        if deadline - time.perf_counter() >= timeout_s:
            pair = _inventory_server(_inventory_store(data_dir))
            server, thread = pair
            try:
                if deadline - time.perf_counter() < timeout_s:
                    warm_rows.extend(
                        _empty_inventory_sample(sample_number, "insufficient runtime budget for request timeout")
                        for sample_number in range(1, samples + 1)
                    )
                else:
                    _get_json(server.url + route_path, timeout=timeout_s)  # unmeasured warm-up
                    for sample_number in range(1, samples + 1):
                        if deadline - time.perf_counter() < timeout_s:
                            warm_rows.append(_empty_inventory_sample(sample_number, "insufficient runtime budget for request timeout"))
                            continue
                        row = _measure_inventory_request(
                            data_dir, route_name, route_path, timeout_s, server_pair=pair, deadline=deadline
                        )
                        row["sample"] = sample_number
                        warm_rows.append(row)
                        if row.get("observed_count") not in (None, size):
                            row["status"] = "count_mismatch"
                            row["expected_count"] = size
            except Exception as exc:
                warm_rows.append({"sample": 0, "status": "error", "error_type": type(exc).__name__})
                warm_rows.extend(
                    _empty_inventory_sample(sample_number, "warm-up request failed")
                    for sample_number in range(1, samples + 1)
                )
            finally:
                _close_inventory_server(server, thread)
        else:
            warm_rows = [
                _empty_inventory_sample(sample_number, "insufficient runtime budget for request timeout")
                for sample_number in range(1, samples + 1)
            ]
        warm[route_name] = _summarize_inventory_rows(warm_rows)
    return cold, warm


def _summarize_inventory_rows(rows: list[dict]) -> dict:
    successful = [row["elapsed_ms"] for row in rows if row.get("status") == "ok"]
    summary = summarize_samples(successful)
    if len(successful) < MIN_P95_SAMPLES:
        summary["p95_ms_nearest_rank"] = None
        summary["p95_unavailable_reason"] = (
            f"p95 requires at least {MIN_P95_SAMPLES} successful samples; "
            f"{len(successful)} completed"
        )
    summary["sample_order"] = rows
    summary["failed_samples"] = sum(row.get("status") != "ok" for row in rows)
    summary["degraded_sections"] = sum(row.get("degraded_sections", 0) for row in rows)
    return summary


def _peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value * 1024 if sys.platform.startswith("linux") else value)


def _run_inventory_size(size: int, samples: int, timeout_s: int, deadline: float) -> dict:
    workspace = Path(tempfile.mkdtemp(prefix=f"skillsmgr-inventory-{size}-"))
    original_environment = {key: os.environ.get(key) for key in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA")}
    try:
        os.environ["HOME"] = str(workspace / "home")
        os.environ["XDG_DATA_HOME"] = str(workspace / "xdg")
        os.environ.pop("SKILLS_MANAGER_DATA", None)
        store, fixture = _build_inventory_fixture(size, workspace)
        cold, warm = _sample_inventory_routes(store.data_dir, size, samples, timeout_s, deadline)
        complete = all(
            stats["sample_count"] == samples and stats["failed_samples"] == 0
            for group in (cold, warm)
            for stats in group.values()
        )
        return {
            "size": size,
            "status": "complete" if complete else "incomplete",
            "fixture": fixture,
            "cold": cold,
            "warm": warm,
        }
    except Exception as exc:
        return {
            "size": size,
            "status": "failed",
            "failure": {"type": type(exc).__name__},
        }
    finally:
        for key, value in original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(workspace, ignore_errors=True)


def run_full_inventory(samples: int = FULL_INVENTORY_SAMPLES,
                       timeout_s: int = INVENTORY_REQUEST_TIMEOUT_S,
                       runtime_limit_s: int = INVENTORY_RUNTIME_LIMIT_S) -> dict:
    """Measure bounded full inventories; fixture creation is outside timings."""
    started = time.perf_counter()
    deadline = started + runtime_limit_s
    sizes = [
        _run_inventory_size(size, samples, timeout_s, deadline)
        for size in FULL_INVENTORY_SIZES
    ]
    return {
        "schema": "skillsmgr-full-inventory-baseline-v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "complete" if all(item["status"] == "complete" for item in sizes) else "incomplete",
        "telemetry": "none",
        "sizes": sizes,
        "measurement": {
            "samples_per_mode_and_route": samples,
            "routes": FULL_INVENTORY_ROUTES,
            "percentile": "nearest rank: sorted[ceil(0.95 * n) - 1]; median uses statistics.median",
            "p95_minimum_successful_samples": MIN_P95_SAMPLES,
            "cold_policy": "new Store wrapper and WebAppServer for each measured request; same Python process; fixture and SQLite resync already complete",
            "warm_policy": "one unmeasured request, then repeated requests on one Store and WebAppServer per route",
            "filesystem_cache_policy": "OS page cache is not flushed; cold means application state reset, not disk-cold",
            "sample_order": "cold routes in declaration order with samples 1..N, then warm routes in declaration order with one warm-up and samples 1..N",
            "request_timeout_s": timeout_s,
            "runtime_limit_s": runtime_limit_s,
            "runtime_policy": "Do not start a request unless its full configured timeout fits before the measurement deadline.",
            "fixture_limits": {
                "max_skills": MAX_INVENTORY_SKILLS,
                "max_file_bytes": MAX_INVENTORY_FILE_BYTES,
                "max_total_bytes": MAX_INVENTORY_TOTAL_BYTES,
            },
            "peak_rss_bytes": _peak_rss_bytes(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine(),
            "cpu_count": os.cpu_count(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }


def _build_fixture(kind: str, workspace: Path) -> tuple[Store, dict]:
    if kind not in FIXTURE_PLAN:
        raise ValueError(f"unknown fixture {kind!r}")
    data_dir = workspace / "data"
    store = Store(data_dir=data_dir)
    store.init_db()
    skills_dir = store.skills_dir
    spec = FIXTURE_PLAN[kind]
    if kind == "small":
        for index in range(12):
            _write_skill(skills_dir, f"baseline-skill-{index:02d}", "A baseline skill for repeatable UI measurement.")
    elif kind == "divergent":
        home = workspace / "home"
        identical_a = home / ".agents" / "skills"
        identical_b = home / ".claude" / "skills"
        _write_skill(skills_dir, "shared-skill", "The same skill in several roots.", "shared body")
        _write_skill(identical_a, "shared-skill", "The same skill in several roots.", "shared body")
        _write_skill(identical_b, "shared-skill", "The same skill in several roots.", "different body")
        _write_skill(skills_dir, "only-global", "Only in the manager store.")
    elif kind == "malformed":
        _write_skill(skills_dir, "valid-skill", "A valid baseline skill.")
        broken = skills_dir / "malformed-skill"
        broken.mkdir(parents=True, exist_ok=True)
        (broken / "SKILL.md").write_text(
            "---\nname: malformed-skill\ndescription: [unterminated\n---\n",
            encoding="utf-8",
        )
    elif kind == "large":
        for index in range(2000):
            _write_skill(
                skills_dir,
                f"baseline-skill-{index:04d}",
                "A deterministic large-library fixture skill.",
            )
    store.resync()
    if kind == "divergent":
        # HOME is set by run_fixture before scope discovery; these are the
        # expected merged-view observations, not private-user data.
        os.environ["HOME"] = str(workspace / "home")
    return store, {
        "kind": kind,
        "description": spec["description"],
        "expected_skill_count": spec["skill_count"],
        "expected_states": list(spec["expected_states"]),
    }


def _get_json(url: str, timeout: int = 15) -> tuple[dict | list, float]:
    started = time.perf_counter()
    with urlopen(url, timeout=timeout) as response:
        body = response.read()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return json.loads(body.decode("utf-8")), elapsed_ms


def run_fixture(kind: str) -> dict:
    """Build one fixture and return its reproducible probe report."""
    original_home = os.environ.get("HOME")
    workspace = Path(tempfile.mkdtemp(prefix=f"skillsmgr-baseline-{kind}-"))
    server = None
    thread = None
    try:
        os.environ["HOME"] = str(workspace / "home")
        store, fixture = _build_fixture(kind, workspace)
        server = WebAppServer(store, port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        probes = []
        for route in (
            "/api/scopes",
            "/api/skills?scope=all",
            "/api/stats",
            "/api/doctor?scope=all",
        ):
            payload, elapsed_ms = _get_json(server.url + route)
            probes.append(
                {
                    "route": route,
                    "elapsed_ms": elapsed_ms,
                    "items": len(payload) if isinstance(payload, list) else None,
                    "keys": sorted(payload) if isinstance(payload, dict) else None,
                }
            )
        skills = next((p for p in probes if p["route"] == "/api/skills?scope=all"), {})
        fixture["observed_skill_rows"] = skills.get("items", 0)
        fixture["probes"] = probes
        fixture["environment"] = {
            "python": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.name,
            "fixture_workspace": str(workspace),
        }
        return fixture
    finally:
        if server is not None:
            server.shutdown()
        if thread is not None:
            thread.join(timeout=5)
        if original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = original_home
        shutil.rmtree(workspace, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=["all", *FIXTURE_PLAN], default="all")
    parser.add_argument("--output", type=Path, help="write JSON evidence to this path")
    parser.add_argument(
        "--full-inventory",
        action="store_true",
        help="intentionally measure 100, 1,000, and 10,000 real skill files",
    )
    parser.add_argument(
        "--samples", type=int, default=FULL_INVENTORY_SAMPLES,
        help="samples per mode and route for --full-inventory (minimum 20)",
    )
    parser.add_argument("--timeout-s", type=int, default=INVENTORY_REQUEST_TIMEOUT_S)
    parser.add_argument("--runtime-limit-s", type=int, default=INVENTORY_RUNTIME_LIMIT_S)
    args = parser.parse_args()
    started = time.perf_counter()
    if args.full_inventory:
        if args.samples < FULL_INVENTORY_SAMPLES or args.samples > 100:
            parser.error("--samples must be between 20 and 100 for --full-inventory")
        if args.timeout_s < 1 or args.timeout_s > 300:
            parser.error("--timeout-s must be between 1 and 300")
        if args.runtime_limit_s < 30 or args.runtime_limit_s > 3600:
            parser.error("--runtime-limit-s must be between 30 and 3600")
        report = run_full_inventory(args.samples, args.timeout_s, args.runtime_limit_s)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0 if report["status"] == "complete" else 1
    names = list(FIXTURE_PLAN) if args.fixture == "all" else [args.fixture]
    report = {
        "schema": "skillsmgr-baseline-v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "telemetry": "none",
        "fixtures": [run_fixture(name) for name in names],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
import shutil
import tempfile
import time
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


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


def _get_json(url: str) -> tuple[dict | list, float]:
    started = time.perf_counter()
    with urlopen(url, timeout=15) as response:
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
    args = parser.parse_args()
    started = time.perf_counter()
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

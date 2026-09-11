"""File-based, advisory-only eval harness (Agent Skills eval contract).

The official "Evaluating skill output quality" guide keeps hand-authored cases
in ``evals/evals.json`` inside a skill directory, runs each case with and
without the skill, and records the results as files in an ``iteration-N/``
workspace (``eval-<slug>/{with_skill,without_skill}/`` holding ``outputs/``,
``timing.json``, and ``grading.json`` plus an aggregate benchmark).

This module implements that file contract with the standard library only: no
network access, no SDK, no third-party runner, no SQLite row, and no ``Store``
method.  Results are advisory — a score never gates an install or an edit.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .atomic_io import atomic_write_text
from .path_safety import contained_path
from .validator import validate_skill_name

EVALS_DIRNAME = "evals"
EVALS_FILENAME = "evals.json"
WORKSPACE_SUFFIX = "-workspace"
OUTPUTS_DIRNAME = "outputs"
OUTPUT_FILENAME = "output.txt"
GRADING_FILENAME = "grading.json"
TIMING_FILENAME = "timing.json"
BENCHMARK_FILENAME = "benchmark.json"

# ``with_skill`` versus ``without_skill`` (or a previous skill version) is the
# baseline pattern the guide prescribes.
VARIANTS = ("with_skill", "without_skill", "previous_version")
DEFAULT_VARIANT = "with_skill"
BASELINE_VARIANT = "without_skill"

ASSERTION_TYPES = ("equals", "contains", "not_contains", "regex", "is_json")

MAX_CASES = 100
MAX_CASE_TEXT = 20000
MAX_OUTPUT_TEXT = 200000
MAX_RUNS = 400
MAX_EVALS_FILE_BYTES = 1_000_000
MAX_PATTERN_LENGTH = 200
MAX_REGEX_INPUT = 50_000
MAX_SLUG_LENGTH = 48

EVAL_POLICY = (
    "advisory-only: results are files in the run workspace, never SQLite rows, "
    "and never gate installs or edits"
)

_WHITESPACE_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def evals_file(skill_dir: Path) -> Path:
    """Return the hand-authored case file path for one skill directory."""
    return Path(skill_dir) / EVALS_DIRNAME / EVALS_FILENAME


def workspace_for(data_dir: Path, name: str) -> Path:
    """Return the default run workspace for an installed skill.

    The workspace lives beside ``skills/`` (never inside it) so the skill scan,
    ``doctor`` orphan detection, and export never see eval run data.
    """
    return Path(data_dir) / EVALS_DIRNAME / f"{validate_skill_name(name)}{WORKSPACE_SUFFIX}"


def workspace_beside(skill_dir: Path) -> Path:
    """Return the guide's authoring layout: ``<skill-dir>-workspace``."""
    skill_dir = Path(skill_dir)
    return skill_dir.parent / f"{skill_dir.name}{WORKSPACE_SUFFIX}"


def _is_within(path: Path, root: Path) -> bool:
    """Return True when *path* resolves inside *root*."""
    candidate = Path(path).resolve()
    resolved_root = Path(root).resolve()
    try:
        return candidate.is_relative_to(resolved_root)
    except AttributeError:  # Python < 3.9 fallback
        return candidate == resolved_root or str(candidate).startswith(str(resolved_root) + "/")


def workspace_for_dir(skill_dir: Path, data_dir: Path, name: str) -> Path:
    """Resolve a workspace for a skill addressed by directory.

    Authoring layouts (a repo checkout, where ``--path`` points outside the
    managed store) keep the guide's beside-the-skill workspace. A directory
    inside the store's ``skills/`` must NOT get a sibling workspace — the skill
    scan, ``doctor`` orphan detection, and export would treat it as skill data —
    so it falls back to ``<data>/evals/<name>-workspace``.
    """
    skill_dir = Path(skill_dir)
    if _is_within(skill_dir, Path(data_dir) / "skills"):
        return workspace_for(data_dir, name)
    return workspace_beside(skill_dir)


def iteration_dir(workspace: Path, iteration: int = 1) -> Path:
    """Return ``<workspace>/iteration-N`` after validating the number."""
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
        raise ValueError("iteration must be a positive integer")
    return Path(workspace) / f"iteration-{iteration}"


def _case_text(value: object, label: str, limit: int = MAX_CASE_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"eval case {label} must be a non-empty string")
    if len(value) > limit:
        raise ValueError(f"eval case {label} exceeds {limit} characters")
    return value


def _case_files(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"eval case {label} must be a list of relative paths")
    files: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"eval case {label} entries must be non-empty strings")
        text = item.strip()
        if text.startswith(("/", "\\")) or ".." in Path(text).parts or "\\" in text:
            raise ValueError(f"eval case {label} entry must stay inside the skill directory: {item!r}")
        files.append(text)
    return files


def _assertions(value: object) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("eval case assertions must be a list")
    normalized: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each eval assertion must be a dict")
        kind = item.get("type")
        if kind not in ASSERTION_TYPES:
            raise ValueError(f"unsupported assertion type {kind!r} (use one of {', '.join(ASSERTION_TYPES)})")
        entry: dict = {"type": kind}
        if kind == "regex":
            pattern = item.get("value")
            if not isinstance(pattern, str) or not pattern:
                raise ValueError("a regex assertion needs a non-empty 'value' pattern")
            if len(pattern) > MAX_PATTERN_LENGTH:
                raise ValueError(f"regex assertion pattern exceeds {MAX_PATTERN_LENGTH} characters")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex assertion pattern: {exc}") from exc
            entry["value"] = pattern
        elif kind != "is_json":
            entry["value"] = _case_text(item.get("value"), "assertion value", MAX_CASE_TEXT)
        if item.get("value") is not None and kind == "is_json":
            entry["value"] = item["value"]
        if item.get("case_sensitive") is True:
            entry["case_sensitive"] = True
        normalized.append(entry)
    return normalized


def normalize_case(case: object, index: int) -> dict:
    """Validate and normalize one eval case from ``evals.json``."""
    if not isinstance(case, dict):
        raise ValueError("each eval case must be an object")
    raw_id = case.get("id", index + 1)
    if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
        raise ValueError("eval case id must be an integer or string")
    if isinstance(raw_id, str) and not raw_id.strip():
        raise ValueError("eval case id must not be blank")
    slug = case.get("slug")
    return {
        "id": raw_id if not isinstance(raw_id, str) else raw_id.strip(),
        "prompt": _case_text(case.get("prompt"), "prompt"),
        "expected_output": _case_text(case.get("expected_output"), "expected_output"),
        "files": _case_files(case.get("files"), "files"),
        "assertions": _assertions(case.get("assertions")),
        "slug": slug.strip().lower() if isinstance(slug, str) and slug.strip() else None,
    }


def load_cases(skill_dir: Path) -> dict:
    """Read ``evals/evals.json`` for a skill (never raises on bad content)."""
    path = evals_file(skill_dir)
    report: dict = {
        "present": False,
        "path": str(path),
        "skill_name": None,
        "cases": [],
        "issues": [],
        "policy": EVAL_POLICY,
    }
    if not path.is_file():
        return report
    report["present"] = True
    try:
        size = path.stat().st_size
        if size > MAX_EVALS_FILE_BYTES:
            raise ValueError(f"evals.json exceeds {MAX_EVALS_FILE_BYTES} bytes")
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        report["issues"].append({"level": "error", "message": f"evals.json is unreadable: {exc}"})
        return report
    if not isinstance(document, dict):
        report["issues"].append({"level": "error", "message": "evals.json must contain a JSON object"})
        return report
    skill_name = document.get("skill_name")
    if skill_name is not None and not isinstance(skill_name, str):
        report["issues"].append({"level": "error", "message": "skill_name must be a string"})
    else:
        report["skill_name"] = skill_name
    raw_cases = document.get("evals")
    if not isinstance(raw_cases, list) or not raw_cases:
        report["issues"].append({"level": "error", "message": "evals must be a non-empty list of cases"})
        return report
    if len(raw_cases) > MAX_CASES:
        report["issues"].append({"level": "error", "message": f"evals has more than {MAX_CASES} cases"})
        return report
    seen: set[object] = set()
    for index, case in enumerate(raw_cases):
        try:
            normalized = normalize_case(case, index)
        except ValueError as exc:
            report["issues"].append({"level": "error", "message": f"case {index + 1}: {exc}"})
            continue
        if normalized["id"] in seen:
            report["issues"].append({"level": "error", "message": f"case {index + 1}: duplicate id {normalized['id']!r}"})
            continue
        seen.add(normalized["id"])
        missing = [entry for entry in normalized["files"] if not (Path(skill_dir) / entry).is_file()]
        if missing:
            report["issues"].append({
                "level": "warning",
                "message": f"case {normalized['id']}: input file(s) not found: {', '.join(missing)}",
            })
        report["cases"].append(normalized)
    return report


def case_slugs(cases: list[dict]) -> list[str]:
    """Return the guide's ``eval-<slug>`` directory name for each case."""
    slugs: list[str] = []
    for index, case in enumerate(cases):
        base = case.get("slug")
        if not base:
            prompt = str(case.get("prompt", ""))
            base = "-".join(_SLUG_RE.sub(" ", prompt.lower()).split()[:6])
        base = _SLUG_RE.sub("-", str(base).lower()).strip("-")[:MAX_SLUG_LENGTH].strip("-")
        if not base:
            base = f"case-{case.get('id', index + 1)}"
        candidate = f"eval-{base}"
        if candidate in slugs:
            candidate = f"{candidate}-{case.get('id', index + 1)}"
        slugs.append(candidate)
    return slugs


def case_dir(workspace: Path, iteration: int, slug: str) -> Path:
    """Return the contained directory for one graded case."""
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError(f"invalid eval case slug {slug!r}")
    return contained_path(iteration_dir(workspace, iteration), slug)


def variant_dir(workspace: Path, iteration: int, slug: str, variant: str) -> Path:
    """Return the contained ``with_skill``/``without_skill`` directory."""
    if variant not in VARIANTS:
        raise ValueError(f"unsupported eval variant {variant!r} (use one of {', '.join(VARIANTS)})")
    return contained_path(case_dir(workspace, iteration, slug), variant)


def _normalize_output(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _assertion_result(assertion: dict, output: str) -> dict:
    kind = assertion["type"]
    case_sensitive = assertion.get("case_sensitive") is True
    haystack = output if case_sensitive else output.lower()
    if kind == "is_json":
        try:
            parsed = json.loads(output)
        except ValueError as exc:
            return {"type": kind, "passed": False, "detail": f"output is not JSON: {exc}"}
        if "value" in assertion:
            expected = assertion["value"]
            passed = parsed == expected
            return {"type": kind, "passed": passed, "detail": "parsed JSON matches expected value" if passed else "parsed JSON differs from expected value"}
        return {"type": kind, "passed": True, "detail": "output parses as JSON"}
    needle = str(assertion.get("value", ""))
    if kind == "regex":
        try:
            match = re.search(needle, output[:MAX_REGEX_INPUT])
        except re.error as exc:  # pragma: no cover - patterns are pre-validated
            return {"type": kind, "passed": False, "detail": f"invalid pattern: {exc}"}
        return {"type": kind, "passed": match is not None,
                "detail": "pattern matched" if match else "pattern not found"}
    if not case_sensitive:
        needle = needle.lower()
    if kind == "equals":
        passed = _normalize_output(haystack) == _normalize_output(needle)
        return {"type": kind, "passed": passed,
                "detail": "normalized text matches" if passed else "normalized text differs"}
    if kind == "contains":
        passed = needle in haystack
        return {"type": kind, "passed": passed,
                "detail": "substring present" if passed else "substring missing"}
    passed = needle not in haystack
    return {"type": kind, "passed": passed,
            "detail": "substring absent" if passed else "forbidden substring present"}


def grade_output(case: dict, output: str) -> dict:
    """Grade one run output against a case's deterministic assertions."""
    if not isinstance(output, str):
        raise ValueError("eval output must be a string")
    if len(output) > MAX_OUTPUT_TEXT:
        raise ValueError(f"eval output exceeds {MAX_OUTPUT_TEXT} characters")
    assertions = case.get("assertions") or []
    results = [_assertion_result(assertion, output) for assertion in assertions]
    passed = sum(1 for result in results if result["passed"])
    return {
        "case": case.get("id"),
        "graded": bool(results),
        "passed": passed if results else None,
        "total": len(results),
        "assertions": results,
    }


def normalize_runs(cases: list[dict], runs: object) -> list[dict]:
    """Validate caller-supplied runs against the loaded eval cases."""
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs must be a non-empty list of run objects")
    if len(runs) > MAX_RUNS:
        raise ValueError(f"runs exceeds {MAX_RUNS} entries")
    known = {case.get("id"): case for case in cases}
    normalized: list[dict] = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise ValueError(f"run {index + 1} must be an object")
        case_id = run.get("case")
        if case_id not in known:
            raise ValueError(f"run {index + 1} references unknown eval case {case_id!r}")
        variant = run.get("variant", DEFAULT_VARIANT)
        if variant not in VARIANTS:
            raise ValueError(f"run {index + 1} has unsupported variant {variant!r} (use one of {', '.join(VARIANTS)})")
        output = run.get("output")
        if not isinstance(output, str):
            raise ValueError(f"run {index + 1} output must be a string")
        if len(output) > MAX_OUTPUT_TEXT:
            raise ValueError(f"run {index + 1} output exceeds {MAX_OUTPUT_TEXT} characters")
        normalized.append({
            "case": case_id,
            "variant": variant,
            "output": output,
            "duration_ms": _optional_number(run.get("duration_ms"), f"run {index + 1} duration_ms"),
            "tokens": _optional_number(run.get("tokens"), f"run {index + 1} tokens"),
        })
    return normalized


def _optional_number(value: object, label: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{label} must be a non-negative number")
    return value


def _pass_rate(graded: int, passed: int) -> float | None:
    if not graded:
        return None
    return round(passed / graded, 4)


def benchmark(cases: list[dict], runs: list[dict]) -> dict:
    """Aggregate graded runs into a per-variant benchmark with a baseline delta."""
    variants: dict[str, dict] = {}
    for run in runs:
        case = next((entry for entry in cases if entry.get("id") == run["case"]), None)
        if case is None:
            continue
        graded = grade_output(case, run["output"])
        bucket = variants.setdefault(run["variant"], {
            "cases": 0, "graded": 0, "cases_passed": 0,
            "assertions_passed": 0, "assertions_total": 0,
        })
        bucket["cases"] += 1
        if graded["graded"]:
            bucket["graded"] += 1
            bucket["assertions_passed"] += graded["passed"] or 0
            bucket["assertions_total"] += graded["total"]
            if graded["passed"] == graded["total"]:
                bucket["cases_passed"] += 1
    for bucket in variants.values():
        bucket["pass_rate"] = _pass_rate(bucket["graded"], bucket["cases_passed"])
    default_rate = (variants.get(DEFAULT_VARIANT) or {}).get("pass_rate")
    baseline_rate = (variants.get(BASELINE_VARIANT) or {}).get("pass_rate")
    delta = None
    if default_rate is not None and baseline_rate is not None:
        delta = round(default_rate - baseline_rate, 4)
    return {
        "variants": variants,
        "delta": delta,
        "delta_meaning": f"{DEFAULT_VARIANT} case pass rate minus {BASELINE_VARIANT} case pass rate",
        "pass_rate_meaning": "cases whose every assertion passed / graded cases",
        "ungraded_cases": sum(1 for case in cases if not (case.get("assertions") or [])),
        "policy": EVAL_POLICY,
        "advisory": True,
    }


def score_runs(cases: list[dict], runs: object) -> dict:
    """Grade every run and return results plus the aggregate benchmark."""
    normalized = normalize_runs(cases, runs)
    results = []
    for run in normalized:
        case = next(entry for entry in cases if entry.get("id") == run["case"])
        graded = grade_output(case, run["output"])
        results.append({**graded, "variant": run["variant"],
                        "duration_ms": run["duration_ms"], "tokens": run["tokens"]})
    return {"runs": results, "benchmark": benchmark(cases, normalized),
            "policy": EVAL_POLICY}


def _write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_runs(workspace: Path, iteration: int, cases: list[dict], runs: object) -> dict:
    """Write outputs, grading, timing, and the benchmark into the workspace.

    Only the run workspace is written: skill files, the SQLite index, and the
    trash are untouched, so a score can never block or alter an install.
    """
    normalized = normalize_runs(cases, runs)
    slugs = case_slugs(cases)
    slug_by_id = {case.get("id"): slugs[index] for index, case in enumerate(cases)}
    scored = score_runs(cases, runs)
    written: list[str] = []
    for result, run in zip(scored["runs"], normalized):
        slug = slug_by_id.get(run["case"])
        target = variant_dir(workspace, iteration, slug, run["variant"])
        output_path = target / OUTPUTS_DIRNAME / OUTPUT_FILENAME
        atomic_write_text(output_path, run["output"])
        written.append(str(output_path))
        _write_json(target / GRADING_FILENAME, {
            "case": run["case"], "variant": run["variant"],
            "graded": result["graded"], "passed": result["passed"],
            "total": result["total"], "assertions": result["assertions"],
            "policy": EVAL_POLICY,
        })
        written.append(str(target / GRADING_FILENAME))
        _write_json(target / TIMING_FILENAME, {
            "duration_ms": run["duration_ms"], "tokens": run["tokens"],
            "recorded_at": _now_iso(),
        })
        written.append(str(target / TIMING_FILENAME))
    benchmark_path = iteration_dir(workspace, iteration) / BENCHMARK_FILENAME
    _write_json(benchmark_path, scored["benchmark"])
    written.append(str(benchmark_path))
    return {
        "iteration": iteration,
        "workspace": str(iteration_dir(workspace, iteration)),
        "written": written,
        "benchmark": scored["benchmark"],
        "runs": scored["runs"],
        "policy": EVAL_POLICY,
    }

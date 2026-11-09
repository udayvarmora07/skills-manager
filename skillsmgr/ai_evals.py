"""AI eval runner (docs/39 A8): does this skill actually help?

Runs a global skill's own ``evals/evals.json`` cases through the user's model
twice: once with the skill's instructions as the system prompt
(``with_skill``) and once without (``without_skill``).  Outputs go through
the existing file-based harness (``evals.record_runs``), which grades them
with the case's deterministic assertions and writes the usual iteration
workspace and ``benchmark.json``.  Nothing here grades with a model, so the
pass rates are exactly as reliable as the assertions the author wrote.

When the model passes the cases just as well without the skill, the result
says so: the skill may no longer be needed for this model (Anthropic's
"capability uplift" check).  Advisory only; scores never gate anything.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import evals
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _save_run
from .errors import StoreError
from .path_safety import contained_path
from .validator import validate_skill_name

MAX_CASES_PER_RUN = 20
MAX_INPUT_FILE_CHARS = 8_000
MAX_EVAL_OUTPUT = 1_500
_BASE = ("You are an AI coding agent working for a developer. Answer the request "
         "directly and completely.")


def _skill_dir(store, name: str) -> Path:
    validate_skill_name(name if isinstance(name, str) else "")
    directory = contained_path(store.skills_dir, name)
    if not directory.is_dir():
        raise AiError(f"{name!r} is not in your library; evals run on library skills", "ai-input")
    return directory


def _cases(skill_dir: Path, limit) -> list[dict]:
    report = evals.load_cases(skill_dir)
    if not report["present"]:
        raise AiError("this skill has no evals/evals.json; add cases first", "ai-input")
    errors = [i["message"] for i in report["issues"] if i["level"] == "error"]
    if errors:
        raise AiError(f"evals.json has problems: {errors[0]}", "ai-input")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_CASES_PER_RUN:
        raise AiError(f"max_cases must be 1 to {MAX_CASES_PER_RUN}", "ai-input")
    return report["cases"][:limit]


def _case_prompt(skill_dir: Path, case: dict) -> str:
    parts = [case["prompt"]]
    for entry in case["files"]:
        try:
            text = contained_path(skill_dir, entry).read_text(encoding="utf-8")[:MAX_INPUT_FILE_CHARS]
        except (OSError, UnicodeDecodeError, ValueError, StoreError):
            continue
        parts.append(f"\n\nInput file {entry}:\n" + untrusted_block(f"input {entry}", text))
    return "".join(parts)


def _next_iteration(workspace: Path) -> int:
    numbers = []
    try:
        for child in workspace.iterdir():
            if child.name.startswith("iteration-") and child.name[10:].isdigit():
                numbers.append(int(child.name[10:]))
    except OSError:
        pass
    return max(numbers, default=0) + 1


def _run_case(run: AiRun, system: str, prompt: str, case_id, variant: str) -> dict | None:
    started = time.monotonic()
    before = run.output_tokens
    text = run.ask_text(system, prompt, max_output=MAX_EVAL_OUTPUT)
    if text is None:
        return None
    return {"case": case_id, "variant": variant, "output": text[:evals.MAX_OUTPUT_TEXT],
            "duration_ms": round((time.monotonic() - started) * 1000),
            "tokens": run.output_tokens - before}


def _verdict(bench: dict) -> str:
    variants = bench.get("variants") or {}
    with_rate = (variants.get("with_skill") or {}).get("pass_rate")
    without = (variants.get("without_skill") or {}).get("pass_rate")
    if with_rate is None or without is None:
        return "ungraded"
    if without >= 1.0 and with_rate >= 1.0:
        return "not-needed"
    if with_rate > without:
        return "helps"
    return "no-gain" if with_rate == without else "hurts"


def run_evals(store, payload: dict) -> dict:
    """Run a library skill's eval cases with and without it and record the results."""
    payload = payload if isinstance(payload, dict) else {}
    name = payload.get("name")
    skill_dir = _skill_dir(store, name)
    cases = _cases(skill_dir, payload.get("max_cases") or 10)
    body = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace") \
        if (skill_dir / "SKILL.md").is_file() else ""
    if not body:
        raise AiError("this skill's SKILL.md cannot be read (it may be turned off)", "ai-input")
    run = AiRun(store.data_dir, "eval-run", estimate_only=bool(payload.get("estimate")))
    with_system = _BASE + "\n\nFollow this skill whenever it applies:\n\n" + body
    runs = []
    for case in cases:
        prompt = _case_prompt(skill_dir, case)
        for system, variant in ((with_system, "with_skill"), (_BASE, "without_skill")):
            row = _run_case(run, system, prompt, case["id"], variant)
            if row:
                runs.append(row)
    where = ("a model running on this machine" if run.config["local"]
             else f"{run.config['label']} ({run.config['base_url']})")
    result = {"kind": "eval-run", "scope": "global", "name": name, "cases": len(cases),
              "egress": [f"{name}'s SKILL.md and {len(cases)} eval prompts (with their input "
                         f"files) go to {where}, each case twice (with and without the skill)."]}
    if not run.estimate_only:
        workspace = evals.ensure_workspace_outside(evals.workspace_for(store.data_dir, name), store.data_dir)
        recording = evals.record_runs(workspace, _next_iteration(workspace), cases, runs)
        result.update({"iteration": recording["iteration"], "benchmark": recording["benchmark"],
                       "results": [{k: r.get(k) for k in ("case", "variant", "graded", "passed", "total",
                                                          "duration_ms", "tokens")}
                                   for r in recording["runs"]],
                       "verdict": _verdict(recording["benchmark"])})
    result["run"] = run.label()
    if not run.estimate_only:
        result["run_id"] = _save_run(store.data_dir, result)
    return result

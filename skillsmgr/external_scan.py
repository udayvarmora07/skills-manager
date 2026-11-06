"""Optional, advisory evidence from an external skill scanner (SkillSpector).

NVIDIA SkillSpector (https://github.com/NVIDIA/SkillSpector) is a separate
program the user may install. It is **never imported**: this module only runs
an installed ``skillspector`` executable, so the CLI stays stdlib-only and no
runtime dependency is added.

Contract, all of it pinned by ``tests/test_external_scan.py``:

* Opt-in only. Callers run a scan when the request asked for one.
* The executable must pass ``launcher_security.trusted_executable``; an unsafe or
  missing PATH match reports ``unavailable`` and is never run.
* The tool scans a private *copy* of the candidate, never the staged review tree
  and never a URL, so it cannot alter what a later commit applies.
* No ``--transitive``, ``--use-shipped-baseline``, ``--recursive`` or
  ``--baseline``: a skill author's baseline must not suppress findings.
* Static mode passes ``--no-llm`` and a scrubbed environment, so no credential
  reaches the tool. LLM mode ("bring your own key") additionally passes only the
  provider variables in ``_LLM_ENV``, read from this process's environment; the
  key is never stored, logged or returned.
* Output is bounded (time, report bytes, findings, string length) and reduced to
  a whitelist. ``code_snippet`` is dropped: it is untrusted skill text.
* Every result is advisory. The tool's own score and recommendation are reported
  as *its* claim (``reported``) and never gate an install, an update or
  ``valid``.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .atomic_io import tree_content_hash
from .launcher_security import trusted_executable
from .store import StoreError

TOOL = "SkillSpector"
EXECUTABLE = "skillspector"
TIMEOUT_STATIC = 120
TIMEOUT_LLM = 600
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_FINDINGS = 200
MAX_TEXT = 500
STDERR_TAIL = 2048
POLICY = "advisory-only; third-party heuristic evidence, not a safety or trust verdict"
EGRESS_STATIC = "dependency names and versions the skill declares may be sent to api.osv.dev"
EGRESS_LLM = "skill file contents are sent to the LLM provider configured by SKILLSPECTOR_PROVIDER"

_BASE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "USERPROFILE")
# Provider variables documented by `skillspector scan --help` (v2.12.0).
_LLM_ENV = (
    "SKILLSPECTOR_PROVIDER", "SKILLSPECTOR_MODEL", "SKILLSPECTOR_REASONING_EFFORT",
    "SKILLSPECTOR_TEMPERATURE", "SKILLSPECTOR_MAX_LLM_CONCURRENCY",
    "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_PROXY_API_KEY", "ANTHROPIC_PROXY_ENDPOINT_URL",
    "AWS_PROFILE", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "NVIDIA_INFERENCE_KEY",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
    "SKILLSPECTOR_COMPAT_API_KEY", "SKILLSPECTOR_COMPAT_BASE_URL", "SKILLSPECTOR_COMPAT_HEADERS",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
    "OLLAMA_BASE_URL",
)
_ISSUE_TEXT = ("id", "category", "pattern", "severity", "finding", "explanation", "remediation")


def scan_options(value: object) -> dict | None:
    """Normalise an opt-in value from CLI, JSON or a form field.

    ``None``/``False``/``""`` (an empty form field) mean no scan; ``True``/``"static"`` a static scan;
    ``"llm"`` or ``{"llm": true}`` an LLM-assisted scan. Anything else is a
    clean ``StoreError`` rather than a silent default.
    """
    if value is None or value is False or value == "":
        return None
    if value is True or value == "static":
        return {"llm": False}
    if value == "llm":
        return {"llm": True}
    if isinstance(value, dict) and set(value) <= {"llm"} and isinstance(value.get("llm", False), bool):
        return {"llm": bool(value.get("llm", False))}
    raise StoreError('external_scan must be true, "static", "llm" or {"llm": true|false}')


def _result(status: str, *, llm: bool, reason: str | None = None) -> dict:
    return {
        "tool": TOOL,
        "status": status,
        "policy": POLICY,
        "mode": "llm" if llm else "static",
        "egress": [EGRESS_STATIC] + ([EGRESS_LLM] if llm else []),
        "reason": reason,
        "version": None,
        "reported": None,
        "coverage": None,
        "llm": None,
        "findings": [],
        "omitted": 0,
        "scanned_tree_hash": None,
    }


def _text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)[:MAX_TEXT]


def _number(value: object) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _child_env(llm: bool) -> dict:
    names = _BASE_ENV + (_LLM_ENV if llm else ())
    return {name: os.environ[name] for name in names if name in os.environ}


def _private_copy(candidate: Path, work: Path) -> Path:
    """Copy the candidate so the tool can neither alter nor race the review tree."""
    copy = work / "skill"
    shutil.copytree(candidate, copy, symlinks=True)
    disabled = copy / "SKILL.md.disabled"
    if disabled.is_file() and not (copy / "SKILL.md").exists():
        disabled.rename(copy / "SKILL.md")
    return copy


def _terminate(process: subprocess.Popen) -> None:
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        pass
    process.wait()


def _run(argv: list[str], *, llm: bool, cwd: Path, stderr_path: Path, timeout: float) -> int | None:
    """Run the tool; return its exit code, or ``None`` on timeout."""
    extra = {"start_new_session": True} if os.name != "nt" else {}
    with open(stderr_path, "wb") as stderr:
        process = subprocess.Popen(  # nosec B603 - trusted absolute path, argv list, no shell
            argv, cwd=cwd, env=_child_env(llm), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=stderr, **extra,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate(process)
            return None


def _stderr_tail(path: Path) -> str:
    try:
        data = path.read_bytes()[-STDERR_TAIL:]
    except OSError:
        return ""
    return data.decode("utf-8", "replace").strip()


def _load_report(path: Path) -> dict | None:
    try:
        if path.stat().st_size > MAX_REPORT_BYTES:
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return report if isinstance(report, dict) else None


def _finding(issue: dict) -> dict:
    location = issue.get("location") if isinstance(issue.get("location"), dict) else {}
    evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
    tags = issue.get("tags") if isinstance(issue.get("tags"), list) else []
    finding = {key: _text(issue.get(key)) for key in _ISSUE_TEXT}
    finding.update({
        "confidence": _number(issue.get("confidence")),
        "file": _text(location.get("file")),
        "line": _number(location.get("start_line")),
        "llm_review": _text(evidence.get("llm_review_outcome")),
        "llm_unconfirmed": "llm-unconfirmed" in tags,
    })
    return finding


def _summarise(report: dict, result: dict) -> dict:
    risk = report.get("risk_assessment") if isinstance(report.get("risk_assessment"), dict) else {}
    meta = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    completeness = report.get("analysis_completeness")
    completeness = completeness if isinstance(completeness, dict) else {}
    provenance = meta.get("llm_provenance") if isinstance(meta.get("llm_provenance"), dict) else {}
    provider = provenance.get("provider") if isinstance(provenance.get("provider"), dict) else {}
    issues = [item for item in report.get("issues") or [] if isinstance(item, dict)]
    result.update({
        "version": _text(meta.get("skillspector_version")),
        "reported": {
            "score": _number(risk.get("score")),
            "severity": _text(risk.get("severity")),
            "recommendation": _text(risk.get("recommendation")),
        },
        "coverage": {
            "percent": _number(completeness.get("coverage_percent")),
            "complete": completeness.get("is_complete") is True,
            "status": _text(completeness.get("status")),
        },
        "llm": {
            "requested": meta.get("llm_requested") is True,
            "available": meta.get("llm_available") is True,
            "provider": _text(provider.get("name")),
            "model": _text(provider.get("model")),
        },
        "findings": [_finding(issue) for issue in issues[:MAX_FINDINGS]],
        "omitted": max(0, len(issues) - MAX_FINDINGS),
    })
    if not result["coverage"]["complete"]:
        result["status"] = "incomplete"
    return result


def _unavailable_reason() -> str:
    """Say whether the tool is absent or present-but-untrusted, without running it."""
    found = shutil.which(EXECUTABLE)
    if not found:
        return "skillspector is not installed on PATH"
    return (
        f"skillspector at {found} was not run: the file or a parent directory is "
        "writable by group/other users or not owned by you (fix with chmod g-w,o-w)"
    )


def skillspector_evidence(candidate: str | Path, *, llm: bool = False,
                          timeout: float | None = None) -> dict:
    """Scan one candidate skill directory and return bounded advisory evidence.

    Never raises for tool problems: a missing tool, a timeout, an error exit or
    an unreadable report each become a ``status`` the caller shows as-is.
    """
    executable = trusted_executable(EXECUTABLE)
    if executable is None:
        return _result("unavailable", llm=llm, reason=_unavailable_reason())
    limit = timeout if timeout is not None else (TIMEOUT_LLM if llm else TIMEOUT_STATIC)
    work = Path(tempfile.mkdtemp(prefix="skillsmgr-extscan-"))
    try:
        os.chmod(work, 0o700)
        try:
            copy = _private_copy(Path(candidate), work)
        except OSError:
            return _result("error", llm=llm, reason="candidate could not be copied for scanning")
        result = _result("completed", llm=llm)
        result["scanned_tree_hash"] = tree_content_hash(copy)
        report_path = work / "report.json"
        argv = [executable, "scan", str(copy), "--format", "json", "--output", str(report_path)]
        if not llm:
            argv.append("--no-llm")
        try:
            code = _run(argv, llm=llm, cwd=work, stderr_path=work / "stderr.txt", timeout=limit)
        except OSError:
            return _result("error", llm=llm, reason="skillspector could not be started")
        if code is None:
            return _result("timeout", llm=llm, reason=f"skillspector did not finish within {limit:g} s")
        report = _load_report(report_path) if code in (0, 1) else None
        if report is None:
            tail = _stderr_tail(work / "stderr.txt")
            reason = f"skillspector exited {code}" if code not in (0, 1) else "skillspector report was missing, too large or not JSON"
            return _result("error", llm=llm, reason=(f"{reason}: {tail}" if tail else reason)[:MAX_TEXT])
        return _summarise(report, result)
    finally:
        shutil.rmtree(work, ignore_errors=True)

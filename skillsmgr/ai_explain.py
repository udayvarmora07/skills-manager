"""AI risk-finding explainer for an installed skill (docs/39 A6).

The findings come first and without AI: ``risk.risk_scan`` over the skill's
document and its bounded file listing, exactly as a review would scan it.
The model then gives a second opinion per finding.

Evidence rules:

* **Demote-only.** An opinion is shown beside the finding it is about.  It
  never changes the finding's severity and never hides it.
* An opinion that a finding is a false positive must quote text that occurs
  in the file it names.  An uncited or mis-cited one becomes ``unclear`` and is
  counted, so the explainer can withhold judgement but not invent a reason.
* With no findings no model call is made; estimate mode sends nothing.
* Read-only: the skill is not touched.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _items, _save_run
from .risk import risk_file_listing, risk_scan
from .validator import validate_skill_name

MAX_FINDINGS = 30
MAX_BODY_CHARS = 20_000
MAX_FILE_CHARS = 6_000
MAX_FILES = 15
_OPINIONS = ("likely-real", "likely-false-positive", "unclear")
_DOCUMENT = "SKILL.md"

_SYSTEM = (
    "You give a second opinion on advisory findings from a pattern scanner that "
    "flagged text in an AI coding-agent skill. For each finding say whether it is "
    "likely a real concern or likely a false positive (for example, a warning that "
    "tells the reader not to do the flagged thing). Back a false-positive opinion "
    "with an exact quote from the named file. Return only JSON."
)


def _record(scope_id, name) -> dict:
    try:
        validate_skill_name(name if isinstance(name, str) else "")
        return scopes.get_skill(scope_id, name)
    except Exception as exc:  # noqa: BLE001 - unknown scope or missing skill is user input
        raise AiError(f"cannot read {name!r} in {scope_id!r}: {exc}", "ai-input") from None


def _files(record: dict) -> list[dict]:
    path = record.get("path")
    return risk_file_listing(path) if isinstance(path, str) and path else []


def _texts(record: dict, files: list[dict]) -> dict[str, str]:
    """The quotable text the model sees: the document body and script files."""
    texts = {_DOCUMENT: str(record.get("body") or "")[:MAX_BODY_CHARS]}
    for entry in files:
        if len(texts) > MAX_FILES:
            break
        if isinstance(entry.get("contents"), str):
            texts[str(entry["path"])] = entry["contents"][:MAX_FILE_CHARS]
    return texts


def _prompt(record: dict, findings: list[dict], texts: dict[str, str]) -> str:
    listed = "\n".join(
        f"[{i}] {f.get('severity', '?')} {f.get('kind', '')}: "
        f"{f.get('why') or ''} | matched: {f.get('evidence') or ''}"[:500]
        for i, f in enumerate(findings))
    parts = [untrusted_block(f"file {path}", text) for path, text in texts.items()]
    return (f"Skill: {record.get('name', '')}\nDescription: {record.get('description') or '(none)'}\n\n"
            + "\n\n".join(parts)
            + "\n\nScanner findings:\n" + untrusted_block("findings", listed)
            + '\n\nAnswer as JSON: {"opinions":[{"index":0,"opinion":"likely-real|likely-false-positive|unclear",'
              '"why":"<one sentence>","file":"<path>","quote":"<exact text from that file>"}]}')


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _opinion(item: dict, findings: list[dict], texts: dict[str, str]) -> tuple[dict | None, bool]:
    """One checked opinion, and whether a false-positive claim was demoted."""
    index = item.get("index")
    if not isinstance(index, int) or not 0 <= index < len(findings) or item.get("opinion") not in _OPINIONS:
        return None, False
    opinion, path, quote = item["opinion"], item.get("file"), _norm(item.get("quote"))
    cited = len(quote) >= 6 and path in texts and quote in _norm(texts[path])
    demoted = opinion == "likely-false-positive" and not cited
    finding = findings[index]
    row = {"index": index, "finding_kind": finding.get("kind"), "finding_severity": finding.get("severity"),
           "opinion": "unclear" if demoted else opinion, "why": str(item.get("why") or "")[:300]}
    if cited:
        row.update(file=path, quote=str(item.get("quote"))[:300])
    return row, demoted


def _opinions(answer, findings: list[dict], texts: dict[str, str]) -> dict:
    out, seen, demoted, dropped = [], set(), 0, 0
    for item in _items(answer, "opinions"):
        row, was_demoted = _opinion(item, findings, texts)
        if row is None or row["index"] in seen:
            dropped += 1
            continue
        seen.add(row["index"])
        demoted += was_demoted
        out.append(row)
    return {"opinions": sorted(out, key=lambda r: r["index"]),
            "uncited_demoted": demoted, "dropped_opinions": dropped}


def explain_findings(data_dir: Path, payload: dict) -> dict:
    """Scan one installed skill, then ask the model for demote-only opinions."""
    payload = payload if isinstance(payload, dict) else {}
    scope_id, name = payload.get("scope"), payload.get("name")
    record = _record(scope_id, name)
    files = _files(record)
    findings = risk_scan({**record, "files": files})
    total = len(findings)
    findings = findings[:MAX_FINDINGS]
    result = {"kind": "explain-findings", "scope": scope_id, "name": name,
              "findings": findings, "findings_total": total, "findings_shown": len(findings),
              "policy": "Opinions are advice beside each finding; no severity is changed and no finding is hidden."}
    if not findings:
        return {**result, "clean": True, "opinions": []}
    texts = _texts(record, files)
    run = AiRun(data_dir, "explain-findings", estimate_only=bool(payload.get("estimate")))
    answer = run.ask_json(_SYSTEM, _prompt(record, findings, texts), max_output=2_000)
    result.update({"clean": False, "files_sent": sorted(texts), "run": run.label(),
                   "egress": [f"{name}'s document and {len(texts) - 1} script file(s) (bounded) and "
                              f"{len(findings)} finding(s) go to the configured model."]})
    if answer is not None:
        result.update(_opinions(answer, findings, texts))
        result["run_id"] = _save_run(data_dir, result)
    return result

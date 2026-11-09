"""AI review briefing (docs/39 A5) for registry fetches and source updates.

Turns a pending review's evidence into a short plain-language briefing:
what the change does, new capabilities it brings (network, shell, credential
or file access), whether the description matches the behaviour, and a second
opinion on each advisory risk finding.

Evidence rules:

* Every claim must quote text that appears in the file it names.  Claims whose
  quote cannot be found are dropped and counted, so the briefing can omit
  but not invent.
* The risk opinion is **demote-only advice**: it is shown beside the original
  finding, never changes its severity, and never hides it.
* The free-text summary cannot be checked and is labelled as such; the raw
  diff stays one click away in the review it accompanies.
* Read-only: the review, its candidate and the target are not touched.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import registry, source_update
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _items, _save_run

MAX_EVIDENCE_CHARS = 40_000
MAX_FILE_CHARS = 8_000
MAX_FILES = 25
MAX_FINDINGS = 20
_KINDS = ("network", "shell", "credentials", "file-write", "persistence", "other")
_MATCH = ("yes", "partly", "no", "unclear")
_OPINIONS = ("likely-real", "likely-false-positive", "unclear")

_SYSTEM = (
    "You brief a developer who must decide whether to install or update an AI "
    "coding-agent skill. Report only what the evidence shows, and back every claim "
    "with an exact quote from the named file. Be specific about network access, shell "
    "commands, credentials and files the skill touches. Return only JSON."
)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n[…truncated]"


def _candidate_texts(directory: Path) -> dict[str, str]:
    """Readable text files of a staged candidate, bounded; links are not followed."""
    out: dict[str, str] = {}
    root = directory / "candidate"
    if not root.is_dir() or root.is_symlink():
        return out
    for path in sorted(root.rglob("*")):
        if len(out) >= MAX_FILES:
            break
        if path.is_symlink() or not path.is_file():
            continue
        try:
            raw = path.read_bytes()[:MAX_FILE_CHARS * 4]
            out[path.relative_to(root).as_posix()] = raw.decode("utf-8")[:MAX_FILE_CHARS]
        except (OSError, UnicodeDecodeError):
            continue
    return out


def _update_evidence(data_dir: Path, review_id: str) -> dict:
    public = source_update.read_update_review(data_dir, review_id)
    directory, _record = source_update._load_record(  # noqa: SLF001 - same package, read-only
        source_update._data_path(data_dir), review_id)  # noqa: SLF001
    staged = _candidate_texts(directory)
    files: dict[str, str] = {}
    for change in (public.get("comparison") or {}).get("changed_files", []):
        path = change.get("path")
        if change.get("status") == "changed" and isinstance(change.get("diff"), list):
            files[path] = "\n".join(str(line) for line in change["diff"])
        elif change.get("status") == "added" and path in staged:
            files[path] = staged[path]
        elif change.get("status") == "removed":
            files[path] = "(file removed)"
    return {"title": f"update to {public.get('target', {}).get('name', 'a skill')}",
            "files": files, "findings": (public.get("risk") or {}).get("findings") or [],
            "description": _skill_description(staged.get("SKILL.md", "")),
            "kind_note": "Changed files are shown as unified diffs ('+' added, '-' removed lines)."}


def _registry_evidence(data_dir: Path, review_id: str) -> dict:
    record = registry.read_registry_review(data_dir, review_id)
    snapshot = record.get("snapshot") or {}
    files = {e["path"]: e["contents"][:MAX_FILE_CHARS] for e in snapshot.get("files", [])[:MAX_FILES]
             if isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("contents"), str)}
    inspection = record.get("inspection") or {}
    risk = inspection.get("risk") if isinstance(inspection.get("risk"), dict) else {}
    return {"title": f"new skill {snapshot.get('id') or snapshot.get('slug') or ''}".strip(),
            "files": files, "findings": risk.get("findings") or [],
            "description": _skill_description(files.get("SKILL.md", "")),
            "kind_note": "These are the complete files of a skill not yet installed."}


def _skill_description(text: str) -> str:
    match = re.search(r"^description:\s*(.+)$", text, re.M)
    return match.group(1).strip().strip("'\"") if match else ""


def _evidence_text(evidence: dict) -> str:
    budget, parts = MAX_EVIDENCE_CHARS, []
    for path, text in evidence["files"].items():
        chunk = untrusted_block(f"file {path}", _clip(text, min(MAX_FILE_CHARS, max(budget, 0))))
        budget -= len(chunk)
        parts.append(chunk)
        if budget <= 0:
            break
    findings = "\n".join(f"[{i}] {f.get('severity', '?')} {f.get('kind', '')}: {f.get('why') or f.get('evidence') or ''}"[:400]
                         for i, f in enumerate(evidence["findings"][:MAX_FINDINGS]) if isinstance(f, dict))
    return (f"This is a {evidence['title']}. {evidence['kind_note']}\n"
            f"Declared description: {evidence['description'] or '(none)'}\n\n" + "\n\n".join(parts)
            + ("\n\nAdvisory risk findings from a pattern scanner:\n" + untrusted_block("findings", findings)
               if findings else "")
            + '\n\nAnswer as JSON: {"summary":"<3 sentences>",'
              '"claims":[{"text":"<what changes or what it does>","file":"<path>","quote":"<exact text>"}],'
              '"capabilities":[{"kind":"network|shell|credentials|file-write|persistence|other",'
              '"detail":"<one sentence>","file":"<path>","quote":"<exact text>"}],'
              '"description_matches":"yes|partly|no|unclear",'
              '"mismatches":[{"text":"<what the description omits or overstates>","file":"<path>","quote":"<exact text>"}],'
              '"finding_opinions":[{"index":0,"opinion":"likely-real|likely-false-positive|unclear","why":"<one sentence>"}]}')


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?m)^[+\- ]", "", str(text))).strip().lower()


def _cited(items: list[dict], files: dict[str, str], extra: tuple[str, ...] = ()) -> tuple[list[dict], int]:
    """Keep items whose quote really occurs in the file they name."""
    kept, dropped = [], 0
    normalized = {path: _norm(text) for path, text in files.items()}
    for item in items[:12]:
        quote, path = _norm(item.get("quote", "")), item.get("file")
        if len(quote) >= 6 and path in normalized and quote in normalized[path]:
            row = {"file": path, "quote": str(item["quote"])[:300],
                   "text": str(item.get("text") or item.get("detail") or "")[:400]}
            for key in extra:
                row[key] = item.get(key)
            kept.append(row)
        else:
            dropped += 1
    return kept, dropped


def _opinions(answer, findings: list) -> list[dict]:
    out = []
    for item in _items(answer, "finding_opinions"):
        index = item.get("index")
        if isinstance(index, int) and 0 <= index < min(len(findings), MAX_FINDINGS) \
                and item.get("opinion") in _OPINIONS:
            finding = findings[index] if isinstance(findings[index], dict) else {}
            out.append({"index": index, "finding_kind": finding.get("kind"),
                        "finding_severity": finding.get("severity"),
                        "opinion": item["opinion"], "why": str(item.get("why") or "")[:300]})
    return out


def _brief(answer, evidence: dict) -> dict:
    files = evidence["files"]
    claims, d1 = _cited(_items(answer, "claims"), files)
    caps, d2 = _cited(_items(answer, "capabilities"), files, ("kind",))
    for cap in caps:
        cap["kind"] = cap["kind"] if cap["kind"] in _KINDS else "other"
    mismatches, d3 = _cited(_items(answer, "mismatches"), files)
    match = answer.get("description_matches") if isinstance(answer, dict) else None
    summary = answer.get("summary") if isinstance(answer, dict) else ""
    return {"summary": re.sub(r"\s+", " ", summary)[:800] if isinstance(summary, str) else "",
            "claims": claims, "capabilities": caps,
            "description_matches": match if match in _MATCH else "unclear",
            "mismatches": mismatches, "finding_opinions": _opinions(answer, evidence["findings"]),
            "dropped_unquoted": d1 + d2 + d3}


def review_briefing(data_dir: Path, payload: dict) -> dict:
    """Brief one pending review (``kind``: ``update`` or ``registry``)."""
    payload = payload if isinstance(payload, dict) else {}
    kind, review_id = payload.get("kind"), payload.get("review_id")
    if kind not in ("update", "registry") or not isinstance(review_id, str) or not review_id:
        raise AiError("give kind 'update' or 'registry' and a review_id", "ai-input")
    loader = _update_evidence if kind == "update" else _registry_evidence
    evidence = loader(Path(data_dir), review_id)
    if not evidence["files"]:
        raise AiError("this review has no readable text changes to brief", "ai-input")
    run = AiRun(data_dir, "review-briefing", estimate_only=bool(payload.get("estimate")))
    answer = run.ask_json(_SYSTEM, _evidence_text(evidence), max_output=2_500)
    where = ("a model running on this machine" if run.config["local"]
             else f"{run.config['label']} ({run.config['base_url']})")
    result = {"kind": "review-briefing", "review_kind": kind, "review_id": review_id,
              "files_sent": sorted(evidence["files"]),
              "egress": [f"The text of {len(evidence['files'])} file(s) from this review"
                         f" (up to {MAX_EVIDENCE_CHARS:,} characters) and its risk findings go to {where}."],
              "notes": ["The summary is the model's wording and is not checked; every listed claim "
                        "quotes the file it names. Risk opinions never change a finding's severity."]}
    if answer is not None:
        result.update(_brief(answer, evidence))
    result["run"] = run.label()
    if answer is not None:
        result["run_id"] = _save_run(data_dir, result)
    return result

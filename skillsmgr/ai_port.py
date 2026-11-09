"""AI porting notes (docs/39 A10): what changes if another agent reads this skill?

The facts are deterministic and come first:

* frontmatter keys the skill carries that the target agent's own documentation
  does not list (``key_support``, cited per consumer);
* references in the body to one agent's conventions (``CLAUDE.md``,
  ``$ARGUMENTS``, ``mcp__`` tool names, ``~/.claude`` paths, named built-in
  tools) found by fixed patterns.

The model only explains those facts and suggests adaptations.  Each note must
name the fact it explains; notes about anything else are dropped.  With no
facts the skill is reported portable and no model call is made.  Read-only.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import key_support, scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _items
from .validator import validate_skill_name

MAX_BODY_CHARS = 4_000
_PATTERNS = (
    ("CLAUDE.md", r"\bCLAUDE\.md\b"), ("AGENTS.md", r"\bAGENTS\.md\b"), ("GEMINI.md", r"\bGEMINI\.md\b"),
    ("$ARGUMENTS", r"\$ARGUMENTS\b"), ("${CLAUDE_*}", r"\$\{?CLAUDE_[A-Z_]+"),
    ("~/.claude path", r"~/\.claude\b|\.claude/"), ("~/.codex path", r"~/\.codex\b|\.codex/"),
    ("MCP tool name", r"\bmcp__[A-Za-z0-9_-]+"),
    ("Claude Code tool name", r"\b(?:TodoWrite|WebFetch|WebSearch|NotebookEdit|MultiEdit)\b"),
    ("subagent", r"\bsub-?agents?\b"),
)


def _keys(record: dict) -> list[str]:
    keys = []
    for part in ("portable_frontmatter", "frontmatter_extensions"):
        mapping = record.get(part)
        if isinstance(mapping, dict):
            keys.extend(k for k in mapping if isinstance(k, str) and k not in keys)
    return keys


def _references(body: str) -> list[dict]:
    found = []
    for label, pattern in _PATTERNS:
        match = re.search(pattern, body, re.I if label == "subagent" else 0)
        if match:
            start = body.rfind("\n", 0, match.start()) + 1
            end = body.find("\n", match.end())
            found.append({"id": f"ref:{label}", "label": label,
                          "line": body[start:end if end != -1 else None].strip()[:200]})
    return found


def porting_facts(record: dict, target: str) -> list[dict]:
    """Deterministic portability facts for one skill and one target consumer."""
    facts = []
    for key in _keys(record):
        if key in ("name", "description"):
            continue
        if not key_support.documents(target, key):
            facts.append({"id": f"key:{key}", "kind": "frontmatter",
                          "detail": f"{key_support.label(target)} does not document the `{key}` key",
                          "documented_elsewhere": key_support.documents_anywhere(key)})
    for ref in _references(record.get("body") or ""):
        facts.append({"id": ref["id"], "kind": "reference", "detail": ref["label"], "line": ref["line"]})
    return facts


_SYSTEM = (
    "You help a developer move an AI coding-agent skill to another agent. Explain each "
    "listed portability fact in plain words and suggest a concrete adaptation. Do not "
    "claim anything about the target agent beyond the facts given. Return only JSON."
)


def porting_notes(data_dir: Path, payload: dict) -> dict:
    """Facts first, then model-written explanations tied to those facts."""
    payload = payload if isinstance(payload, dict) else {}
    scope_id, name, target = payload.get("scope"), payload.get("name"), payload.get("target")
    validate_skill_name(name if isinstance(name, str) else "")
    if target not in key_support.known_consumers():
        raise AiError("choose a target agent: " + ", ".join(key_support.known_consumers()), "ai-input")
    record = _record(scope_id, name)
    facts = porting_facts(record, target)
    result = {"kind": "porting-notes", "scope": scope_id, "name": name, "target": target,
              "target_label": key_support.label(target), "source": key_support.source(target),
              "facts": facts}
    if not facts:
        return {**result, "portable": True, "notes": []}
    run = AiRun(data_dir, "porting-notes", estimate_only=bool(payload.get("estimate")))
    fact_text = "\n".join(f"- {f['id']}: {f['detail']}" + (f" (line: {f['line']})" if f.get("line") else "")
                          for f in facts)
    answer = run.ask_json(_SYSTEM, f"Target agent: {key_support.label(target)}\n\nFacts:\n"
                          + untrusted_block("facts", fact_text)
                          + "\n\nSkill:\n" + untrusted_block("skill", (record.get("body") or "")[:MAX_BODY_CHARS])
                          + '\n\nAnswer as JSON: {"summary":"<two sentences>",'
                            '"notes":[{"fact":"<fact id>","explanation":"...","suggestion":"..."}]}',
                          max_output=1_200)
    result.update({"portable": False, "run": run.label(),
                   "egress": [f"{name}'s body (first {MAX_BODY_CHARS:,} characters) and {len(facts)} "
                              "portability facts go to the configured model."]})
    if answer is not None:
        result.update(_notes(answer, facts))
    return result


def _record(scope_id, name: str) -> dict:
    try:
        return scopes.get_skill(scope_id, name)
    except Exception as exc:  # noqa: BLE001 - unknown scope or missing skill is user input
        raise AiError(f"cannot read {name!r} in {scope_id!r}: {exc}", "ai-input") from None


def _notes(answer, facts: list[dict]) -> dict:
    """Model notes that explain a listed fact; anything else is dropped and counted."""
    ids = {f["id"] for f in facts}
    raw = _items(answer, "notes")
    notes = [{"fact": n["fact"], "explanation": str(n.get("explanation") or "")[:400],
              "suggestion": str(n.get("suggestion") or "")[:400]}
             for n in raw if n.get("fact") in ids]
    summary = answer.get("summary") if isinstance(answer, dict) else ""
    return {"summary": summary[:500] if isinstance(summary, str) else "", "notes": notes,
            "dropped_notes": len(raw) - len(notes)}

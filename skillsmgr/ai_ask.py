"""Ask your library (docs/39 A9): "which of my skills handles X?".

Sends only skill names, descriptions (first 300 characters) and the agents
that hold them -- never bodies.  Large libraries are narrowed first by a
word-overlap prefilter so at most 300 entries reach the model.  Every skill
the answer names is checked against the real listing; invented names are
dropped and counted, so a link in the answer always leads to a real skill.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _items

MAX_QUESTION = 500
MAX_SENT = 300
MAX_MATCHES = 8
_SYSTEM = (
    "You help a developer find skills in their own AI coding-agent skill library. "
    "Recommend only skills from the listing, best first, and say in one sentence why "
    "each fits. If none fits, say so. Return only JSON."
)


def _library(scope_id: str) -> dict[str, dict]:
    """``name -> {description, scopes}`` for enabled, readable skills."""
    records = scopes.list_all() if scope_id == "all" else scopes.scan_scope(scope_id)
    library: dict[str, dict] = {}
    for record in records:
        name = record.get("name")
        if not isinstance(name, str) or record.get("disabled") or record.get("decode_error"):
            continue
        entry = library.setdefault(name, {"description": "", "scopes": []})
        if not entry["description"] and isinstance(record.get("description"), str):
            entry["description"] = re.sub(r"\s+", " ", record["description"]).strip()
        if record.get("scope") not in entry["scopes"]:
            entry["scopes"].append(record.get("scope"))
    return library


def _narrow(library: dict[str, dict], question: str) -> list[str]:
    if len(library) <= MAX_SENT:
        return sorted(library)
    words = set(re.findall(r"[a-z0-9]{3,}", question.lower()))

    def score(name: str) -> int:
        text = (name.replace("-", " ") + " " + library[name]["description"]).lower()
        return sum(1 for w in words if w in text)

    return sorted(library, key=lambda n: (-score(n), n))[:MAX_SENT]


def _question(payload: dict) -> tuple[str, str]:
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise AiError("ask a question", "ai-input")
    scope_id = payload.get("scope") or "all"
    if not isinstance(scope_id, str):
        raise AiError("scope must be a scope id or 'all'", "ai-input")
    return re.sub(r"[\x00-\x1f\x7f]", " ", question).strip()[:MAX_QUESTION], scope_id


def _matches(answer, library: dict[str, dict], sent: list[str]) -> tuple[list[dict], int]:
    """Suggested skills that exist; duplicates skipped, invented names counted."""
    matches, invented, allowed = [], 0, set(sent)
    for item in _items(answer, "skills")[:MAX_MATCHES * 2]:
        name = item.get("name")
        if any(m["name"] == name for m in matches):
            continue
        if name not in allowed:
            invented += 1
            continue
        matches.append({"name": name, "scopes": library[name]["scopes"],
                        "description": library[name]["description"][:300],
                        "why": str(item.get("why") or "")[:300]})
    return matches[:MAX_MATCHES], invented


def ask_library(data_dir: Path, payload: dict) -> dict:
    """Answer a question about the user's skills, citing only real skills."""
    question, scope_id = _question(payload if isinstance(payload, dict) else {})
    library = _library(scope_id)
    if not library:
        raise AiError("no enabled, readable skills to search", "ai-input")
    sent = _narrow(library, question)
    listing = "\n".join(f"- {n} [{', '.join(str(s) for s in library[n]['scopes'])}]: "
                        f"{library[n]['description'][:300]}" for n in sent)
    run = AiRun(data_dir, "ask-library", estimate_only=bool(payload.get("estimate")))
    answer = run.ask_json(_SYSTEM, "Skill listing:\n" + untrusted_block("skill-listing", listing)
                          + "\n\nQuestion:\n" + untrusted_block("question", question)
                          + '\n\nAnswer as JSON: {"answer":"<two sentences>",'
                            '"skills":[{"name":"<exact name>","why":"<one sentence>"}]}',
                          max_output=700)
    where = ("a model running on this machine" if run.config["local"]
             else f"{run.config['label']} ({run.config['base_url']})")
    result = {"kind": "ask-library", "scope": scope_id, "question": question,
              "searched": len(library), "sent": len(sent),
              "egress": [f"Your question and the names and first 300 description characters of "
                         f"{len(sent)} skills go to {where}. No skill bodies are sent."],
              "run": run.label()}
    if answer is not None:
        matches, invented = _matches(answer, library, sent)
        text = answer.get("answer") if isinstance(answer, dict) else ""
        result.update({"answer": re.sub(r"\s+", " ", text)[:600] if isinstance(text, str) else "",
                       "matches": matches, "dropped_unknown": invented})
    return result

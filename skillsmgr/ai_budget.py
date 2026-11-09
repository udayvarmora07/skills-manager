"""AI listing-budget fitter (docs/39 A4).

Agents cap the skill listing they show the model: Claude Code gives it about
1% of the context window and silently drops descriptions past that (docs/26,
claude-code #56710); Codex truncates at 2% (codex #19679).  This feature
measures how far over the budget a listing is, asks the model to shorten only
the largest descriptions, and then re-runs the trigger test with and without
the shortened versions.  A shortened description is marked ``safe`` only if
its skill still wins at least as many of its prompts as before.  Nothing is
written; each proposal is applied through the ordinary edit.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import hygiene, scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import (_egress, _items, _route, _save_run, _summarize, build_listing,
                        generate_prompts, normalize_prompts)

MAX_SKILLS = 10
MIN_TARGET = 120
_SHORTEN_SYSTEM = (
    "You shorten AI coding-agent skill descriptions so more of them fit in the agent's "
    "limited skill listing. Keep what the skill does and the concrete words a developer "
    "would type when it is needed; drop filler, examples lists and marketing. Never add "
    "capabilities. Return only JSON."
)


def _budget(listing: dict, payload: dict) -> dict:
    """Listing size and budget: measured for Claude Code, otherwise caller-supplied."""
    supplied = payload.get("budget_chars")
    if supplied not in (None, ""):
        if isinstance(supplied, bool) or not isinstance(supplied, int) or supplied < 100:
            raise AiError("budget_chars must be a whole number of at least 100", "ai-input")
        return {"listing_chars": listing["chars"], "budget_chars": supplied, "source": "you"}
    if listing["scope"] != "claude-code":
        raise AiError("give a character budget for this agent (only Claude Code's is measured)",
                      "ai-input")
    report = hygiene.hygiene_report(scopes.scan_scope("claude-code"), scope="claude-code")
    section = report.get("claude_listing") or {}
    budget = (section.get("budget") or {}).get("budget_chars_estimate")
    if not isinstance(budget, int) or budget <= 0:
        raise AiError("Claude Code's listing budget could not be estimated; give budget_chars",
                      "ai-input")
    return {"listing_chars": int(section.get("listing_chars") or listing["chars"]),
            "budget_chars": budget, "source": "Claude Code settings estimate"}


def _choose(listing: dict, need: int, limit: int) -> list[dict]:
    """Largest descriptions first, until shortening them could plausibly cover ``need``."""
    chosen, projected = [], 0
    for entry in sorted(listing["entries"], key=lambda e: (-len(e["description"]), e["name"])):
        if len(chosen) >= limit or projected >= need:
            break
        current = len(entry["description"])
        target = max(MIN_TARGET, int(current * 0.45))
        if current - target < 40:
            break
        chosen.append({"name": entry["name"], "current": entry["description"], "target": target})
        projected += current - target
    return chosen


def _shorten(run: AiRun, chosen: list[dict]) -> dict:
    if run.estimate_only:
        return {c["name"]: "x" * c["target"] for c in chosen}
    lines = "\n".join(f"- {c['name']} (at most {c['target']} characters): {c['current']}" for c in chosen)
    answer = run.ask_json(_SHORTEN_SYSTEM, "Descriptions to shorten:\n"
                          + untrusted_block("descriptions", lines)
                          + '\n\nAnswer as JSON: {"shortened":[{"name":"<name>","description":"<shorter>"}]}',
                          max_output=min(4000, sum(c["target"] for c in chosen) // 2 + 300))
    limits = {c["name"]: c for c in chosen}
    out = {}
    for item in _items(answer, "shortened"):
        name, text = item.get("name"), item.get("description")
        if name in limits and isinstance(text, str):
            text = re.sub(r"\s+", " ", text).strip()
            if 20 <= len(text) < len(limits[name]["current"]) and len(text) <= limits[name]["target"] + 40:
                out[name] = text
    if not out:
        raise AiError("the model returned no usable shorter descriptions; try again", "ai-bad-output", 502)
    return out


def _recalls(summary: dict) -> dict:
    return {s["name"]: s["hit_rate"] for s in summary.get("skills", [])}


def _proposals(chosen: list[dict], short: dict, before: dict, after: dict) -> list[dict]:
    rows = []
    for c in chosen:
        if c["name"] not in short:
            continue
        b, a = before.get(c["name"]), after.get(c["name"])
        rows.append({"name": c["name"], "current": c["current"], "proposed": short[c["name"]],
                     "saves_chars": len(c["current"]) - len(short[c["name"]]),
                     "recall_before": b, "recall_after": a,
                     "safe": a is not None and b is not None and a >= b})
    return rows


def fit_budget(data_dir: Path, payload: dict) -> dict:
    """Propose verified shorter descriptions until the listing could fit its budget."""
    payload = payload if isinstance(payload, dict) else {}
    listing = build_listing(payload.get("scope") or "claude-code")
    budget = _budget(listing, payload)
    need = max(0, budget["listing_chars"] - budget["budget_chars"])
    result = {"kind": "fit-budget", "scope": listing["scope"], **budget, "chars_to_free": need}
    if need == 0:
        return {**result, "status": "within-budget", "proposals": []}
    limit = payload.get("max_skills") or 5
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SKILLS:
        raise AiError(f"max_skills must be 1 to {MAX_SKILLS}", "ai-input")
    chosen = _choose(listing, need, limit)
    if not chosen:
        return {**result, "status": "nothing-to-shorten", "proposals": []}
    run = AiRun(data_dir, "fit-budget", estimate_only=bool(payload.get("estimate")))
    short = _shorten(run, chosen)
    names = {e["name"] for e in listing["entries"]}
    prompts = normalize_prompts(generate_prompts(run, listing, list(short), per_skill=3), names)
    before = _summarize(listing, prompts, [_route(run, listing, prompts, {}, 0)])
    after = _summarize(listing, prompts, [_route(run, listing, prompts, short, 0)])
    result.update({"status": "estimate" if run.estimate_only else "proposed",
                   "chosen": [c["name"] for c in chosen],
                   "egress": _egress(listing, len(prompts), [
                       f"The {len(chosen)} largest descriptions are sent to be shortened."], run)})
    if not run.estimate_only:
        proposals = _proposals(chosen, short, _recalls(before), _recalls(after))
        saved = sum(p["saves_chars"] for p in proposals if p["safe"])
        result.update({"proposals": proposals, "safe_savings": saved, "fits": saved >= need})
    result["run"] = run.label()
    if not run.estimate_only:
        result["run_id"] = _save_run(data_dir, result)
    return result

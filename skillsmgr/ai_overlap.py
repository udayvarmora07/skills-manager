"""AI overlap judge (docs/39 A3): which of my skills compete or contradict?

Candidate pairs come from three cheap, deterministic sources so the model is
asked about a bounded number of pairs, never the library squared:

1. ``hygiene.near_duplicate_candidates`` (the existing heuristic);
2. a description-word overlap prefilter that also catches differently named
   skills doing the same job;
3. pairs the user names explicitly.

Each pair is judged twice with the two skills in swapped order.  A verdict that
changes with the order is reported as ``uncertain`` (position-bias control).
Every quoted conflict must appear verbatim in the skill it is attributed to;
quotes that do not are dropped and counted, so the model cannot invent
evidence.  The judge proposes boundary sentences or a merge; it never edits.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import hygiene, scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _items, _save_run, build_listing

MAX_PAIRS = 12
MAX_BODY_CHARS = 2_500
MIN_OVERLAP = 0.18
_RELATIONS = ("same-purpose", "overlapping", "distinct")
_ACTIONS = ("merge", "narrow-descriptions", "keep-both")
_STOP = frozenset("""
this that with when from your have will into about their them they then than what which
use used using skill skills user users code file files make sure also only more most
should would could must does like just need needs want task tasks work works help helps
""".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]{3,}", text.lower()) if w not in _STOP}


def _records_with_bodies(scope_id: str, names: set[str]) -> dict[str, dict]:
    records = {}
    for record in scopes.scan_scope(scope_id):
        name = record.get("name")
        if name in names and name not in records:
            if not isinstance(record.get("body"), str) or not record["body"]:
                try:
                    record = {**record, "body": scopes.get_skill(scope_id, name).get("body") or ""}
                except Exception:  # noqa: BLE001 - an unreadable body still has a description
                    record = {**record, "body": ""}
            records[name] = record
    return records


def candidate_pairs(listing: dict, records: dict[str, dict], explicit: list) -> list[dict]:
    """Bounded candidate pairs, strongest first, each with why it was chosen."""
    pairs: dict[tuple, dict] = {}

    def add(a: str, b: str, source: str, score: float) -> None:
        if a == b or a not in records or b not in records:
            return
        key = tuple(sorted((a, b)))
        entry = pairs.setdefault(key, {"skills": list(key), "sources": [], "score": 0.0})
        if source not in entry["sources"]:
            entry["sources"].append(source)
        entry["score"] = max(entry["score"], score)

    for pair in explicit:
        add(pair[0], pair[1], "chosen", 2.0)
    near = hygiene.near_duplicate_candidates(list(records.values()))
    for item in near["candidates"]:
        left, right = item["records"]
        add(left.get("name"), right.get("name"), "near-duplicate heuristic", 1.0 + item["similarity"])
    words = {e["name"]: _words(e["name"].replace("-", " ") + " " + e["description"])
             for e in listing["entries"]}
    names = sorted(words)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            union = words[a] | words[b]
            score = len(words[a] & words[b]) / len(union) if union else 0.0
            if score >= MIN_OVERLAP:
                add(a, b, "shared description words", score)
    return sorted(pairs.values(), key=lambda p: (-p["score"], p["skills"]))


_JUDGE_SYSTEM = (
    "You review two AI coding-agent skills from the same library. Decide whether an "
    "agent choosing between them would be confused, and whether their instructions "
    "conflict. Quote conflicting instructions exactly as written. Be conservative: "
    "'distinct' when they serve different requests. Return only JSON."
)


def _judge_request(first: dict, second: dict) -> str:
    def block(tag: str, record: dict) -> str:
        text = (f"name: {record['name']}\ndescription: {record.get('description') or ''}\n\n"
                f"{(record.get('body') or '')[:MAX_BODY_CHARS]}")
        return untrusted_block(tag, text)

    return ("Skill A:\n" + block("skill-a", first) + "\n\nSkill B:\n" + block("skill-b", second)
            + '\n\nAnswer as JSON: {"relation":"same-purpose|overlapping|distinct",'
              '"router_confusion":true|false,'
              '"shared_requests":["<a request both could claim>"],'
              '"conflicts":[{"a_quote":"<exact text from A>","b_quote":"<exact text from B>",'
              '"why":"<one sentence>"}],'
              '"recommendation":"merge|narrow-descriptions|keep-both",'
              '"a_boundary":"<one sentence to add to A\'s description, or empty>",'
              '"b_boundary":"<one sentence to add to B\'s description, or empty>",'
              '"merged_description":"<if merge, a description for the merged skill, else empty>"}')


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _verified_conflicts(answer, first: dict, second: dict) -> tuple[list[dict], int]:
    """Keep conflicts whose quotes really occur in the skills they cite."""
    haystack_a = _norm(f"{first.get('description') or ''} {first.get('body') or ''}")
    haystack_b = _norm(f"{second.get('description') or ''} {second.get('body') or ''}")
    kept, dropped = [], 0
    for item in _items(answer, "conflicts")[:6]:
        qa, qb = _norm(item.get("a_quote", "")), _norm(item.get("b_quote", ""))
        if len(qa) >= 8 and len(qb) >= 8 and qa in haystack_a and qb in haystack_b:
            kept.append({"a_quote": str(item["a_quote"])[:300], "b_quote": str(item["b_quote"])[:300],
                         "why": str(item.get("why") or "")[:300]})
        else:
            dropped += 1
    return kept, dropped


def _text(answer, key: str, limit: int) -> str:
    value = answer.get(key) if isinstance(answer, dict) else None
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _one_order(run: AiRun, first: dict, second: dict) -> dict | None:
    answer = run.ask_json(_JUDGE_SYSTEM, _judge_request(first, second), max_output=900)
    if answer is None:
        return None
    relation = answer.get("relation") if isinstance(answer, dict) else None
    conflicts, dropped = _verified_conflicts(answer, first, second)
    shared = [str(s)[:300] for s in (answer.get("shared_requests") or [])
              if isinstance(s, str)][:4] if isinstance(answer, dict) else []
    action = answer.get("recommendation") if isinstance(answer, dict) else None
    return {"relation": relation if relation in _RELATIONS else "unknown",
            "router_confusion": bool(answer.get("router_confusion")) if isinstance(answer, dict) else False,
            "shared_requests": shared, "conflicts": conflicts, "unverified_quotes": dropped,
            "recommendation": action if action in _ACTIONS else "keep-both",
            "boundaries": {first["name"]: _text(answer, "a_boundary", 400),
                           second["name"]: _text(answer, "b_boundary", 400)},
            "merged_description": _text(answer, "merged_description", 1024)}


def _merged_conflicts(forward: list[dict], backward: list[dict]) -> list[dict]:
    """Union of both orders' conflicts, re-oriented so ``a_quote`` is always skill A."""
    merged = list(forward)
    seen = {(_norm(c["a_quote"]), _norm(c["b_quote"])) for c in forward}
    for c in backward:
        key = (_norm(c["b_quote"]), _norm(c["a_quote"]))
        if key not in seen:
            seen.add(key)
            merged.append({"a_quote": c["b_quote"], "b_quote": c["a_quote"], "why": c["why"]})
    return merged


def _combine(forward: dict, backward: dict) -> dict:
    """Merge the two orders; disagreement is reported, never averaged away."""
    consistent = forward["relation"] == backward["relation"]
    return {
        "relation": forward["relation"] if consistent else "uncertain",
        "consistent": consistent,
        "orders": [forward["relation"], backward["relation"]],
        "router_confusion": forward["router_confusion"] and backward["router_confusion"],
        "shared_requests": forward["shared_requests"] or backward["shared_requests"],
        "conflicts": _merged_conflicts(forward["conflicts"], backward["conflicts"]),
        "unverified_quotes": forward["unverified_quotes"] + backward["unverified_quotes"],
        "recommendation": (forward["recommendation"]
                           if forward["recommendation"] == backward["recommendation"] else "review"),
        "boundaries": {k: forward["boundaries"].get(k) or backward["boundaries"].get(k, "")
                       for k in forward["boundaries"]},
        "merged_description": forward["merged_description"] or backward["merged_description"],
    }


def _explicit_pairs(raw) -> list[tuple[str, str]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_PAIRS:
        raise AiError(f"pairs must be a list of at most {MAX_PAIRS} [name, name] entries", "ai-input")
    out = []
    for pair in raw:
        if (not isinstance(pair, list) or len(pair) != 2
                or not all(isinstance(n, str) for n in pair)):
            raise AiError("each pair must be [name, name]", "ai-input")
        out.append((pair[0], pair[1]))
    return out


def overlap_judge(data_dir: Path, payload: dict) -> dict:
    """Find and judge competing or contradicting skill pairs in one scope."""
    payload = payload if isinstance(payload, dict) else {}
    listing = build_listing(payload.get("scope"))
    explicit = _explicit_pairs(payload.get("pairs"))
    limit = payload.get("max_pairs") or 6
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAIRS:
        raise AiError(f"max_pairs must be 1 to {MAX_PAIRS}", "ai-input")
    names = {e["name"] for e in listing["entries"]}
    records = _records_with_bodies(listing["scope"], names)
    candidates = candidate_pairs(listing, records, explicit)
    chosen = candidates[:limit]
    estimate = bool(payload.get("estimate"))
    run = AiRun(data_dir, "overlap-judge", estimate_only=estimate)
    judged = []
    for pair in chosen:
        first, second = (records[n] for n in pair["skills"])
        forward = _one_order(run, first, second)
        backward = _one_order(run, second, first)
        if forward and backward:
            judged.append({**pair, **_combine(forward, backward)})
    where = ("a model running on this machine" if run.config["local"]
             else f"{run.config['label']} ({run.config['base_url']})")
    result = {
        "kind": "overlap-judge", "scope": listing["scope"],
        "candidates_found": len(candidates), "pairs_judged": len(chosen),
        "pairs": [{"skills": p["skills"], "sources": p["sources"], "score": round(p["score"], 3)}
                  for p in chosen],
        "egress": [f"For {len(chosen)} pair{'' if len(chosen) == 1 else 's'}, both skills' names, descriptions and up to "
                   f"{MAX_BODY_CHARS:,} body characters go to {where}, twice (both orders)."],
        "run": run.label(),
    }
    if estimate:
        return result
    order = {"same-purpose": 0, "uncertain": 1, "overlapping": 2, "unknown": 3, "distinct": 4}
    judged.sort(key=lambda j: (order.get(j["relation"], 5), -j["score"]))
    result["judgements"] = judged
    result["run_id"] = _save_run(data_dir, result)
    return result

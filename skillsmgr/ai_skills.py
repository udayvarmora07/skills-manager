"""AI features over a user's skill library (docs/39).

Feature A1 — **trigger test**: rebuild the skill listing one agent sees (names
plus capped descriptions, the whole library as distractors) and ask a model,
playing that agent, which skill it would load for each test prompt.  The
report shows which skills never win their own prompts, which skills steal
others' prompts, and which near-miss prompts trigger something anyway.

Feature A2 — **verified description rewrite**: propose new descriptions for
one skill from its failures, then re-run the trigger test with each candidate
substituted.  A candidate is recommended only when it beats the current
description on prompts it was *not* written from (a held-out half), so a
rewrite that merely memorised its training prompts is never offered.

Both features are read-only.  Applying a rewrite goes through the existing
reviewed edit path (snapshot + Undo); nothing here writes a skill.
"""
from __future__ import annotations

import json
import random
import re
import secrets
import time
from pathlib import Path

from . import scopes
from .ai import AiError, AiRun, untrusted_block
from .atomic_io import atomic_write_text
from .path_safety import mkdir_private
from .validator import validate_skill_name

DESCRIPTION_CAP = 1536          # Claude Code's per-entry listing cap (docs/34)
MAX_LISTED = 600
MAX_TARGETS = 40
MAX_PROMPTS = 120
MAX_PROMPT_CHARS = 600
MAX_REPEATS = 5
BATCH = 10
MAX_BODY_CHARS = 4_000
MAX_CANDIDATES = 3
MAX_DESCRIPTION = 1024
KEEP_RUNS = 50
NONE = "(none)"


# -- the listing ------------------------------------------------------------


def _hidden(record: dict) -> bool:
    if record.get("disabled") or record.get("decode_error") or record.get("document_missing"):
        return True
    if record.get("addressable") is False or record.get("malformed"):
        return True
    for part in ("portable_frontmatter", "frontmatter_extensions"):
        mapping = record.get(part)
        if isinstance(mapping, dict) and mapping.get("disable-model-invocation") is True:
            return True
    return False


def _listing_text(record: dict) -> str:
    description = record.get("description") if isinstance(record.get("description"), str) else ""
    extensions = record.get("frontmatter_extensions")
    when = extensions.get("when_to_use") if isinstance(extensions, dict) else None
    combined = description + ((" " + when) if isinstance(when, str) and when else "")
    return re.sub(r"\s+", " ", combined).strip()


def build_listing(scope_id: str) -> dict:
    """The skills one agent scope offers a model: what it would see."""
    if not isinstance(scope_id, str) or not scope_id or scope_id == "all":
        raise AiError("choose one agent scope to test", "ai-input")
    try:
        records = scopes.scan_scope(scope_id)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean input error
        raise AiError(f"cannot read scope {scope_id!r}: {exc}", "ai-input") from None
    entries, seen, hidden, over_cap = [], set(), 0, []
    for record in records:
        name = record.get("name")
        if not isinstance(name, str) or name in seen:
            continue
        if _hidden(record):
            hidden += 1
            continue
        seen.add(name)
        text = _listing_text(record)
        if len(text) > DESCRIPTION_CAP:
            over_cap.append(name)
        entries.append({"name": name, "description": text[:DESCRIPTION_CAP]})
    if not entries:
        raise AiError("this scope has no enabled, readable skills to test", "ai-input")
    if len(entries) > MAX_LISTED:
        raise AiError(f"this scope lists {len(entries)} skills; the trigger test supports "
                      f"at most {MAX_LISTED}", "ai-input")
    return {"scope": scope_id, "entries": entries, "hidden": hidden, "over_cap": over_cap,
            "chars": sum(len(e["name"]) + len(e["description"]) + 4 for e in entries)}


def _render_listing(entries: list[dict], overrides: dict, order_seed: int) -> str:
    ordered = list(entries)
    random.Random(order_seed).shuffle(ordered)   # position-bias control (docs/39 §5)
    lines = []
    for entry in ordered:
        description = overrides.get(entry["name"], entry["description"])
        lines.append(f"- {entry['name']}: {description[:DESCRIPTION_CAP]}")
    return "\n".join(lines)


# -- input validation -------------------------------------------------------


def _clean_text(value, what: str, limit: int = MAX_PROMPT_CHARS) -> str:
    if not isinstance(value, str):
        raise AiError(f"{what} must be text", "ai-input")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", value).strip()
    if not text:
        raise AiError(f"{what} must not be empty", "ai-input")
    return text[:limit]


def normalize_prompts(raw, names: set[str]) -> list[dict]:
    """``[{text, expected}]`` → validated prompts with stable ids."""
    if not isinstance(raw, list) or not raw:
        raise AiError("give at least one test prompt", "ai-input")
    if len(raw) > MAX_PROMPTS:
        raise AiError(f"at most {MAX_PROMPTS} test prompts per run", "ai-input")
    prompts = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            raise AiError("each prompt must be text or {text, expected}", "ai-input")
        expected = item.get("expected")
        if expected in ("", NONE):
            expected = None
        if expected is not None and expected not in names:
            raise AiError(f"prompt {index + 1} expects {expected!r}, which this scope does "
                          "not list", "ai-input")
        prompts.append({"id": f"p{index + 1}", "text": _clean_text(item.get("text"), "a prompt"),
                        "expected": expected, "split": item.get("split") if item.get("split")
                        in ("train", "holdout") else None})
    return prompts


def _repeats(value) -> int:
    if value in (None, ""):
        return 1
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_REPEATS:
        raise AiError(f"repeats must be 1 to {MAX_REPEATS}", "ai-input")
    return value


# -- prompt generation ------------------------------------------------------

_GEN_SYSTEM = (
    "You write realistic test requests for an AI coding agent's skill router. "
    "Developers type short, concrete requests in their own words; they rarely name "
    "the skill. Return only JSON."
)


def _generation_request(listing: dict, targets: list[str], per_skill: int, near_misses: int) -> str:
    by_name = {e["name"]: e for e in listing["entries"]}
    others = [e["name"] for e in listing["entries"] if e["name"] not in targets][:300]
    described = "\n".join(f"- {t}: {by_name[t]['description']}" for t in targets)
    near = (f"Also write {near_misses} near-miss requests: they look related to these "
            "skills but should NOT load any of them (they belong to another skill or to "
            "none). For each, name the better skill from the other-skills list or null.\n"
            if near_misses else "")
    rest = ("\n\nOther skills the agent has:\n" + untrusted_block("skill-names", ", ".join(others))
            if others else "")
    return (f"Write {per_skill} different requests per skill below that a developer would "
            "type when this skill is the right one to load. Vary wording and difficulty; "
            "include at least one indirect request.\n" + near
            + "\nSkills to test:\n" + untrusted_block("skill-listing", described) + rest
            + '\n\nAnswer as JSON: {"prompts":[{"skill":"<name>","text":"<request>"}],'
              '"near_misses":[{"text":"<request>","better":"<name or null>"}]}')


def _items(answer, key: str) -> list[dict]:
    """The dict items of one list field of a model answer; anything else is dropped."""
    values = answer.get(key) if isinstance(answer, dict) else None
    return [v for v in values if isinstance(v, dict)] if isinstance(values, list) else []


def _parse_generated(answer, targets: list[str], names: set[str]) -> list[dict]:
    prompts = [{"text": item["text"][:MAX_PROMPT_CHARS], "expected": item["skill"]}
               for item in _items(answer, "prompts")
               if item.get("skill") in targets and isinstance(item.get("text"), str)]
    for item in _items(answer, "near_misses"):
        if isinstance(item.get("text"), str):
            better = item.get("better")
            prompts.append({"text": item["text"][:MAX_PROMPT_CHARS],
                            "expected": better if better in names and better not in targets else None})
    if not prompts:
        raise AiError("the model produced no usable prompts; try again", "ai-bad-output", 502)
    return prompts[:MAX_PROMPTS]


def generate_prompts(run: AiRun, listing: dict, targets: list[str], *, per_skill: int = 3,
                     near_misses: int = 0) -> list[dict]:
    """Ask the model for prompts that should (and should not) select each target."""
    names = {e["name"] for e in listing["entries"]}
    targets = [t for t in targets if t in names][:MAX_TARGETS]
    if not targets:
        raise AiError("choose at least one listed skill to generate prompts for", "ai-input")
    per_skill = max(1, min(int(per_skill), 6))
    near_misses = max(0, min(int(near_misses), 10))
    if run.estimate_only:
        filler = "x" * 120
        out = [{"text": filler, "expected": t} for t in targets for _ in range(per_skill)]
        return out + [{"text": filler, "expected": None} for _ in range(near_misses)]
    answer = run.ask_json(_GEN_SYSTEM, _generation_request(listing, targets, per_skill, near_misses),
                          max_output=min(4000, 120 * (per_skill * len(targets) + near_misses) + 200))
    return _parse_generated(answer, targets, names)


# -- the trigger test -------------------------------------------------------

_ROUTER_SYSTEM = (
    "You are an AI coding agent deciding which skill to load before answering a user "
    "request. You can see only the skill listing below: names and descriptions. For each "
    "request, pick the single skill you would load first, or null if none clearly fits. "
    "Also give your second choice or null. Judge only by the descriptions. Return only JSON."
)


def _route(run: AiRun, listing: dict, prompts: list[dict], overrides: dict, seed: int) -> dict:
    """One pass over every prompt; returns ``{prompt_id: (choice, runner_up)}``."""
    names = {e["name"] for e in listing["entries"]}
    rendered = _render_listing(listing["entries"], overrides, seed)
    answers: dict[str, tuple] = {}
    for start in range(0, len(prompts), BATCH):
        batch = prompts[start:start + BATCH]
        requests = "\n".join(json.dumps({"id": p["id"], "request": p["text"]}) for p in batch)
        user = ("Skill listing:\n" + untrusted_block("skill-listing", rendered)
                + "\n\nUser requests (one JSON object per line):\n"
                + untrusted_block("user-requests", requests)
                + '\n\nAnswer as JSON: {"answers":[{"id":"<id>","skill":"<name or null>",'
                  '"runner_up":"<name or null>"}]} with one entry per request id.')
        answer = run.ask_json(_ROUTER_SYSTEM, user, max_output=60 + 45 * len(batch))
        if answer is None:
            continue
        for row in (answer.get("answers") if isinstance(answer, dict) else None) or []:
            if not isinstance(row, dict) or row.get("id") not in {p["id"] for p in batch}:
                continue
            choice = row.get("skill")
            runner = row.get("runner_up")
            answers[row["id"]] = (
                choice if choice in names else (None if choice in (None, "", "null") else "?invalid"),
                runner if runner in names else None,
            )
    return answers


def _tally(prompt: dict, passes: list[dict], tally: dict) -> dict:
    """Count one prompt's choices across passes into a per-prompt row."""
    counts: dict[str, int] = {}
    for answers in passes:
        if prompt["id"] not in answers:
            tally["missing"] += 1
            continue
        choice = answers[prompt["id"]][0]
        tally["invalid"] += choice == "?invalid"
        key = NONE if choice in (None, "?invalid") else choice
        counts[key] = counts.get(key, 0) + 1
    answered = sum(counts.values())
    target = prompt["expected"] or NONE
    hits = counts.get(target, 0)
    return {"id": prompt["id"], "text": prompt["text"], "expected": prompt["expected"],
            "split": prompt.get("split"), "choices": counts,
            "top": max(counts, key=lambda k: (counts[k], k == target)) if counts else None,
            "hit_rate": hits / answered if answered else None, "answered": answered,
            "_hits": hits}


def _accumulate(row: dict, tally: dict, per_skill: dict, focus: str | None) -> None:
    expected, answered, hits = row["expected"], row["answered"], row.pop("_hits")
    positive = expected == focus if focus is not None else bool(expected)
    if positive:
        tally["positives"] += answered
        tally["correct"] += hits
    else:
        tally["negatives"] += answered
        # Single-skill check: only "did the focus skill load" counts as a false trigger.
        tally["false"] += (row["choices"].get(focus, 0) if focus is not None
                           else answered - row["choices"].get(NONE, 0))
    if focus is None and expected:
        stats = per_skill.setdefault(expected, {"prompts": 0, "hits": 0, "answered": 0, "lost_to": {}})
        stats["prompts"] += 1
        stats["hits"] += hits
        stats["answered"] += answered
        for name, n in row["choices"].items():
            if name != expected:
                stats["lost_to"][name] = stats["lost_to"].get(name, 0) + n


def _verdict(rate) -> str:
    if rate is None:
        return "unknown"
    return "never-fires" if rate == 0 else "unreliable" if rate < 0.67 else "fires"


def _skill_rows(per_skill: dict) -> list[dict]:
    rows = []
    for name, stats in sorted(per_skill.items()):
        rate = stats["hits"] / stats["answered"] if stats["answered"] else None
        lost = sorted(stats["lost_to"].items(), key=lambda kv: -kv[1])
        rows.append({"name": name, "prompts": stats["prompts"], "hit_rate": rate,
                     "lost_to": [{"name": k, "count": v} for k, v in lost[:5]],
                     "verdict": _verdict(rate)})
    return rows


def _summarize(listing: dict, prompts: list[dict], passes: list[dict], focus: str | None = None) -> dict:
    """Aggregate repeated passes into per-prompt and per-skill evidence."""
    tally = dict.fromkeys(("positives", "correct", "negatives", "false", "invalid", "missing"), 0)
    per_skill: dict = {}
    rows = []
    for prompt in prompts:
        row = _tally(prompt, passes, tally)
        _accumulate(row, tally, per_skill, focus)
        rows.append(row)
    chosen = {name for row in rows for name in row["choices"] if name != NONE}
    return {
        "prompts": rows,
        "skills": _skill_rows(per_skill),
        "recall": tally["correct"] / tally["positives"] if tally["positives"] else None,
        "false_trigger_rate": tally["false"] / tally["negatives"] if tally["negatives"] else None,
        "never_chosen": sorted(e["name"] for e in listing["entries"]
                               if e["name"] not in chosen and e["name"] in per_skill),
        "invalid_answers": tally["invalid"],
        "missing_answers": tally["missing"],
    }


def _egress(listing: dict, prompts: int, extra: list[str], run: AiRun) -> list[str]:
    where = ("a model running on this machine" if run.config["local"]
             else f"{run.config['label']} ({run.config['base_url']})")
    return [f"Names and descriptions of {len(listing['entries'])} skills in "
            f"{listing['scope']} go to {where}.",
            f"{prompts} test prompts go with them."] + extra


def trigger_test(data_dir: Path, payload: dict) -> dict:
    """Run (or estimate) the trigger test described in the module docstring."""
    payload = payload if isinstance(payload, dict) else {}
    listing = build_listing(payload.get("scope"))
    names = {e["name"] for e in listing["entries"]}
    estimate = bool(payload.get("estimate"))
    run = AiRun(data_dir, "trigger-test", estimate_only=estimate)
    repeats = _repeats(payload.get("repeats"))
    raw = payload.get("prompts")
    generated = False
    if not raw:
        targets = payload.get("generate_for") or []
        if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            raise AiError("generate_for must be a list of skill names", "ai-input")
        if not targets:
            raise AiError("give test prompts, or choose skills to generate prompts for", "ai-input")
        raw = generate_prompts(run, listing, targets, per_skill=payload.get("per_skill") or 3,
                               near_misses=payload.get("near_misses") or 0)
        generated = True
    prompts = normalize_prompts(raw, names)
    passes = [_route(run, listing, prompts, {}, seed) for seed in range(repeats)]
    result = {
        "kind": "trigger-test", "scope": listing["scope"],
        "listed": len(listing["entries"]), "hidden": listing["hidden"],
        "over_cap": listing["over_cap"], "repeats": repeats, "generated_prompts": generated,
        "egress": _egress(listing, len(prompts), [], run),
        "run": run.label(),
    }
    if estimate:
        result["prompt_count"] = len(prompts)
        return result
    result.update(_summarize(listing, prompts, passes))
    result["run"] = run.label()
    result["run_id"] = _save_run(data_dir, result)
    return result


# -- verified description rewrite -------------------------------------------

_REWRITE_SYSTEM = (
    "You improve the description of an AI coding-agent skill. The description is the "
    "only thing the agent reads when deciding whether to load the skill, so it must say "
    "what the skill does and when to use it, using words developers actually type, and "
    "say when NOT to use it if it is being confused with a neighbour. Never invent "
    "capabilities the skill body does not support. Return only JSON."
)


def _split(prompts: list[dict]) -> None:
    """Alternate train / held-out within each expected group, deterministically."""
    counters: dict = {}
    for prompt in prompts:
        key = prompt["expected"]
        n = counters.get(key, 0)
        counters[key] = n + 1
        prompt["split"] = prompt.get("split") or ("train" if n % 2 == 0 else "holdout")


def _score(summary: dict, split: str | None = None) -> dict:
    rows = [r for r in summary["prompts"] if split is None or r.get("split") == split]
    pos = [r for r in rows if r.get("_positive")]
    neg = [r for r in rows if not r.get("_positive")]
    def rate(rs, good):
        answered = sum(r["answered"] for r in rs)
        return sum(good(r) for r in rs) / answered if answered else None
    recall = rate(pos, lambda r: r["choices"].get(r["_focus"], 0))
    avoid = rate(neg, lambda r: r["answered"] - r["choices"].get(r["_focus"], 0))
    parts = [v for v in (recall, avoid) if v is not None]
    return {"recall": recall, "near_miss_avoided": avoid,
            "score": sum(parts) / len(parts) if parts else None}


def _mark(summary: dict, focus: str) -> dict:
    for row in summary["prompts"]:
        row["_focus"] = focus
        row["_positive"] = row["expected"] == focus
    return summary


def _strip_marks(summary: dict) -> dict:
    for row in summary["prompts"]:
        row.pop("_focus", None)
        row.pop("_positive", None)
    return summary


def _rewrite_request(listing: dict, name: str, body: str, baseline: dict, count: int) -> str:
    by_name = {e["name"]: e["description"] for e in listing["entries"]}
    train = [r for r in baseline["prompts"] if r.get("split") == "train"]
    own = [r for r in train if r["expected"] == name]
    misses = [r["text"] for r in own if (r["hit_rate"] or 0) < 1]
    hits = [r["text"] for r in own if (r["hit_rate"] or 0) >= 1]
    stolen = [r["text"] for r in train if r["expected"] != name and r["choices"].get(name)]
    rivals = sorted({k for r in train for k in r["choices"] if k not in (name, NONE)})[:8]
    rival_text = "\n".join(f"- {k}: {by_name.get(k, '')}" for k in rivals)
    section = lambda title, label, lines: (  # noqa: E731 - local formatting helper
        f"\n\n{title}:\n" + untrusted_block(label, "\n".join(lines) or "(none)"))
    return (f"Skill name: {name}\nCurrent description:\n"
            + untrusted_block("current-description", by_name.get(name, ""))
            + "\n\nSkill body (first part):\n" + untrusted_block("skill-body", body[:MAX_BODY_CHARS])
            + section("Requests that SHOULD load it but did not", "missed", misses)
            + section("Requests that already load it", "hit", hits)
            + section("Requests that should NOT load it but did", "false-triggers", stolen)
            + section("Neighbouring skills it competes with", "rivals", [rival_text] if rival_text else [])
            + f"\n\nWrite {count} alternative descriptions, each at most {MAX_DESCRIPTION} "
              "characters, one paragraph, no markdown. Generalise from the requests rather "
              "than copying them. Answer as JSON: "
              '{"candidates":[{"description":"...","rationale":"<one sentence>"}]}')


def _parse_candidates(answer, current: str, count: int) -> list[dict]:
    out = []
    for item in _items(answer, "candidates"):
        if not isinstance(item.get("description"), str):
            continue
        text = re.sub(r"\s+", " ", item["description"]).strip()
        if 20 <= len(text) <= MAX_DESCRIPTION and text != current:
            out.append({"description": text, "rationale": str(item.get("rationale") or "")[:300]})
    if not out:
        raise AiError("the model proposed no usable description; try again", "ai-bad-output", 502)
    return out[:count]


def _candidate_descriptions(run: AiRun, listing: dict, name: str, body: str,
                            baseline: dict, count: int) -> list[dict]:
    if run.estimate_only:
        return [{"description": "x" * 600, "rationale": ""} for _ in range(count)]
    answer = run.ask_json(_REWRITE_SYSTEM, _rewrite_request(listing, name, body, baseline, count),
                          max_output=400 * count + 200)
    current = next((e["description"] for e in listing["entries"] if e["name"] == name), "")
    return _parse_candidates(answer, current, count)


def _improve_inputs(run: AiRun, listing: dict, name: str, payload: dict) -> tuple[list[dict], str]:
    """The prompt set (split train / held-out) and the skill body for one rewrite."""
    names = {e["name"] for e in listing["entries"]}
    raw = payload.get("prompts") or generate_prompts(run, listing, [name], per_skill=6, near_misses=4)
    prompts = normalize_prompts(raw, names)
    if not any(p["expected"] == name for p in prompts):
        raise AiError("at least one prompt must expect this skill", "ai-input")
    _split(prompts)
    try:
        body = scopes.get_skill(listing["scope"], name).get("body") or ""
    except Exception:  # noqa: BLE001 - the description alone is still enough to try
        body = ""
    return prompts, body


def _improves(overall: dict, holdout: dict, base_all: dict, base_hold: dict) -> bool:
    """Recommend only a candidate that wins overall without losing on held-out prompts."""
    if overall["score"] is None or base_all["score"] is None:
        return False
    return (overall["score"] > base_all["score"]
            and (holdout["score"] or 0) >= (base_hold["score"] or 0)
            and (overall["recall"] or 0) >= (base_all["recall"] or 0))


def _ranked(baseline: dict, scored: list[tuple[dict, dict]]) -> dict:
    base_all, base_hold = _score(baseline), _score(baseline, "holdout")
    ranked = []
    for candidate, summary in scored:
        overall, holdout = _score(summary), _score(summary, "holdout")
        ranked.append({**candidate, "overall": overall, "holdout": holdout,
                       "recommended": _improves(overall, holdout, base_all, base_hold),
                       "chars": len(candidate["description"]),
                       "prompts": _strip_marks(summary)["prompts"]})
    ranked.sort(key=lambda c: (c["recommended"], c["overall"]["score"] or 0), reverse=True)
    return {"baseline": {"overall": base_all, "holdout": base_hold,
                         "prompts": _strip_marks(baseline)["prompts"]},
            "candidates": ranked,
            "verdict": "improved" if any(c["recommended"] for c in ranked) else "no-better-candidate"}


def improve_description(data_dir: Path, payload: dict) -> dict:
    """Propose descriptions for one skill and keep only those that measurably help."""
    payload = payload if isinstance(payload, dict) else {}
    name = payload.get("name")
    validate_skill_name(name if isinstance(name, str) else "")
    listing = build_listing(payload.get("scope"))
    current = next((e["description"] for e in listing["entries"] if e["name"] == name), None)
    if current is None:
        raise AiError(f"{name!r} is not an enabled, readable skill in this scope", "ai-input")
    estimate = bool(payload.get("estimate"))
    run = AiRun(data_dir, "improve-description", estimate_only=estimate)
    repeats = _repeats(payload.get("repeats"))
    count = max(1, min(int(payload.get("candidates") or 2), MAX_CANDIDATES))
    prompts, body = _improve_inputs(run, listing, name, payload)

    def evaluate(overrides: dict) -> dict:
        passes = [_route(run, listing, prompts, overrides, seed) for seed in range(repeats)]
        return {} if estimate else _mark(_summarize(listing, prompts, passes, focus=name), name)

    baseline = evaluate({})
    candidates = _candidate_descriptions(run, listing, name, body, baseline or {"prompts": []}, count)
    scored = [(c, evaluate({name: c["description"]})) for c in candidates]
    result = {"kind": "improve-description", "scope": listing["scope"], "name": name,
              "current": current, "prompt_count": len(prompts), "repeats": repeats,
              "egress": _egress(listing, len(prompts), [
                  f"The first {min(len(body), MAX_BODY_CHARS):,} characters of {name}'s body go too."], run)}
    if not estimate:
        result.update(_ranked(baseline, scored))
    result["run"] = run.label()
    if not estimate:
        result["run_id"] = _save_run(data_dir, result)
    return result


# -- run files --------------------------------------------------------------


def _runs_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "ai" / "runs"


def _save_run(data_dir: Path, result: dict) -> str:
    """Keep a copy of a finished run as a file (never SQLite); newest 50 kept."""
    directory = mkdir_private(_runs_dir(data_dir))
    run_id = f"{result['kind']}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{secrets.token_hex(4)}"
    atomic_write_text(directory / f"{run_id}.json", json.dumps(result, indent=1, sort_keys=True))
    try:
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[KEEP_RUNS:]:
            old.unlink(missing_ok=True)
    except OSError:
        pass
    return run_id


def list_runs(data_dir: Path, limit: int = 20) -> list[dict]:
    directory = _runs_dir(data_dir)
    out = []
    try:
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"run_id": path.stem, "kind": data.get("kind"), "scope": data.get("scope"),
                    "name": data.get("name"), "started": (data.get("run") or {}).get("started"),
                    "model": (data.get("run") or {}).get("model")})
    return out


def read_run(data_dir: Path, run_id: str) -> dict:
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-z-]+-\d{8}T\d{6}Z-[0-9a-f]{8}", run_id):
        raise AiError("unknown run id", "ai-input")
    path = _runs_dir(data_dir) / f"{run_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AiError("that run no longer exists", "ai-not-found", 404) from None
    except (OSError, ValueError):
        raise AiError("that run file cannot be read", "ai-input") from None


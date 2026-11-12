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

import hashlib
import json
import random
import re
import secrets
import time
from pathlib import Path

from . import scopes
from .ai import AiError, AiRun, committed_day_tokens, untrusted_block
from .atomic_io import atomic_write_text, mutation_lock
from .path_safety import mkdir_private
from .file_reads import read_regular_file
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
MAX_AI_ARTIFACT_BYTES = 16 * 1024 * 1024
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
    # Reproduce listing permutations for a routing experiment, not a security decision.
    random.Random(order_seed).shuffle(ordered)  # nosec B311 - experimental order control (docs/39 section 5).
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


def _batch_request(batch: list[dict]) -> str:
    requests = "\n".join(json.dumps({"id": p["id"], "request": p["text"]}) for p in batch)
    return ("User requests (one JSON object per line):\n"
            + untrusted_block("user-requests", requests)
            + '\n\nAnswer as JSON: {"answers":[{"id":"<id>","skill":"<name or null>",'
              '"runner_up":"<name or null>"}]} with one entry per request id.')


def _record_answers(answer, batch: list[dict], names: set, answers: dict) -> None:
    ids = {p["id"] for p in batch}
    for row in (answer.get("answers") if isinstance(answer, dict) else None) or []:
        if not isinstance(row, dict) or row.get("id") not in ids:
            continue
        choice = row.get("skill")
        runner = row.get("runner_up")
        answers[row["id"]] = (
            choice if choice in names else (None if choice in (None, "", "null") else "?invalid"),
            runner if runner in names else None,
        )


def _route(run: AiRun, listing: dict, prompts: list[dict], overrides: dict, seed: int) -> dict:
    """One pass over every prompt; returns ``{prompt_id: (choice, runner_up)}``."""
    names = {e["name"] for e in listing["entries"]}
    rendered = _render_listing(listing["entries"], overrides, seed)
    answers: dict[str, tuple] = {}
    listing_text = "Skill listing:\n" + untrusted_block("skill-listing", rendered) + "\n\n"
    # The listing is identical in every batch of this pass: send it as a cacheable
    # prefix, but only when a later batch will read the cache it writes.
    prefix = listing_text if len(prompts) > BATCH else ""
    for start in range(0, len(prompts), BATCH):
        batch = prompts[start:start + BATCH]
        user = _batch_request(batch)
        answer = run.ask_json(_ROUTER_SYSTEM, user if prefix else listing_text + user,
                              max_output=60 + 45 * len(batch), prefix=prefix)
        if answer is not None:
            _record_answers(answer, batch, names, answers)
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


def _fingerprint(value) -> str:
    """Hash ordered JSON data independently of dictionary insertion order."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _trigger_seed(value) -> int:
    if value is None:
        return 0
    if type(value) is not int or not 0 <= value <= 4_294_967_295:
        raise AiError("seed must be an integer from 0 to 4294967295", "ai-input")
    return value


def _trigger_provenance(listing: dict, prompts: list, run: AiRun) -> dict:
    return {"version": 1, "router": "trigger-test-v1",
            "prompt_sha256": _fingerprint([[p["text"], p["expected"]] for p in prompts]),
            "listing_sha256": _fingerprint(listing["entries"]),
            "endpoint_sha256": _fingerprint(run.config["base_url"])}


def _compare_saved_result(payload: dict, source: str) -> bool:
    return source == "saved" and bool(payload.get("compare_previous", True))


def _trigger_routes(run, listing, prompts, repeats, seed):
    return [_route(run, listing, prompts, {}, seed + offset) for offset in range(repeats)]


def _preflight_trigger_budget(run, listing, prompts, repeats, seed):
    """Estimate the captured route requests before a CLI run can spend."""
    if run.estimate_only:
        return
    estimated_before = run.estimated_input
    run.estimate_only = True
    try:
        _trigger_routes(run, listing, prompts, repeats, seed)
        if committed_day_tokens(run.data_dir) + run.estimated_input > run.config["max_day_tokens"]:
            raise AiError("the planned run exceeds today's AI token cap", "ai-budget", 409)
    finally:
        run.estimate_only = False
        run.estimated_input = estimated_before


def trigger_test(data_dir: Path, payload: dict, *, preflight=None) -> dict:
    """Run one input/configuration snapshot; saved-prompt preflight sends nothing."""
    payload = payload if isinstance(payload, dict) else {}
    listing = build_listing(payload.get("scope"))
    listing["entries"] = sorted(listing["entries"], key=lambda entry: entry["name"])
    names = {e["name"] for e in listing["entries"]}
    estimate = bool(payload.get("estimate"))
    run = AiRun(data_dir, "trigger-test", estimate_only=estimate)
    repeats = _repeats(payload.get("repeats"))
    seed = _trigger_seed(payload.get("seed"))
    raw, source = _trigger_prompts(data_dir, run, listing, payload)
    prompts = normalize_prompts(raw, names)
    result = {
        "kind": "trigger-test", "scope": listing["scope"],
        "listed": len(listing["entries"]), "hidden": listing["hidden"],
        "over_cap": listing["over_cap"], "repeats": repeats,
        "seed": seed, "listing_snapshot": listing["entries"],
        "provenance": _trigger_provenance(listing, prompts, run),
        "generated_prompts": source == "generated", "prompt_source": source,
        "egress": _egress(listing, len(prompts), [], run),
        "run": run.label(),
    }
    if preflight is not None:
        preflight(result)
        _preflight_trigger_budget(run, listing, prompts, repeats, seed)
    passes = _trigger_routes(run, listing, prompts, repeats, seed)
    result["run"] = run.label()
    if estimate:
        result["prompt_count"] = len(prompts)
        return result
    return _finish_trigger_run(data_dir, payload, result, listing, prompts, passes, source)


def _finish_trigger_run(data_dir, payload, result, listing, prompts, passes, source):
    result.update(_summarize(listing, prompts, passes))
    if _compare_saved_result(payload, source):
        result["compared_with"], result["changes"] = _compare_with_previous(data_dir, result)
    result["run_id"] = _save_run(data_dir, result)
    return result


def _trigger_prompts(data_dir: Path, run: AiRun, listing: dict, payload: dict) -> tuple[list, str]:
    """Prompts for one trigger test: given, saved regression set, or generated."""
    if payload.get("saved"):
        return _saved_trigger_prompts(data_dir, listing, payload.get("strict_saved")), "saved"
    if payload.get("prompts"):
        return payload["prompts"], "given"
    targets = payload.get("generate_for") or []
    if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
        raise AiError("generate_for must be a list of skill names", "ai-input")
    if not targets:
        raise AiError("give test prompts, or choose skills to generate prompts for", "ai-input")
    return generate_prompts(run, listing, targets, per_skill=payload.get("per_skill") or 3,
                            near_misses=payload.get("near_misses") or 0), "generated"


def _saved_trigger_prompts(data_dir: Path, listing: dict, strict: bool) -> list:
    names = {e["name"] for e in listing["entries"]}
    saved = read_prompt_set(data_dir, listing["scope"])["prompts"]
    if not strict:
        saved = [p for p in saved if p["expected"] is None or p["expected"] in names]
    if not saved:
        raise AiError("no saved regression prompts for this agent yet", "ai-input")
    return saved


# -- regression prompt sets (A7) ---------------------------------------------

MAX_SAVED_PER_SKILL = 20
MAX_SAVED = 500


def _read_ai_json(path: Path) -> dict:
    """Bound private AI artifacts and refuse linked files or AI subdirectories."""
    if path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise AiError("AI artifact directories must not be symlinks", "ai-input")
    # ASCII-escaped JSON for 600 full descriptions can exceed 11 MiB.
    if path.lstat().st_size > MAX_AI_ARTIFACT_BYTES:
        raise AiError("AI artifact exceeds the 16 MiB limit", "ai-input")
    raw = read_regular_file(path, MAX_AI_ARTIFACT_BYTES, follow_symlinks=False)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise AiError("AI artifact must be a JSON object", "ai-input")
    return data


def _prompt_set_path(data_dir: Path, scope_id: str) -> Path:
    if not isinstance(scope_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9:._-]{0,127}", scope_id):
        raise AiError("invalid scope id", "ai-input")
    return Path(data_dir) / "ai" / "prompt-sets" / f"{scope_id.replace(':', '_')}.json"


def read_prompt_set(data_dir: Path, scope_id: str) -> dict:
    """The saved regression prompts for one scope (empty when none)."""
    path = _prompt_set_path(data_dir, scope_id)
    try:
        data = _read_ai_json(path)
    except FileNotFoundError:
        return {"scope": scope_id, "prompts": []}
    except (OSError, ValueError, RecursionError):
        raise AiError("the saved prompt set cannot be read; delete it and save again", "ai-input") from None
    return _decoded_prompt_set(data, scope_id)


def _decoded_prompt_set(data, scope_id: str) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("prompts"), list):
        raise AiError("the saved prompt set must contain a prompts list", "ai-input")
    prompts = data["prompts"]
    if len(prompts) > MAX_SAVED or any(not isinstance(p, dict) or not isinstance(p.get("text"), str)
                                     or not (p.get("expected") is None or isinstance(p.get("expected"), str))
                                     for p in prompts):
        raise AiError("the saved prompt set contains invalid prompts", "ai-input")
    return {"scope": scope_id, "prompts": [{"text": p["text"], "expected": p.get("expected")} for p in prompts]}


def _merge_prompts(current: list, incoming: list, limit: int) -> list:
    seen = {(p["text"], p["expected"]) for p in current}
    per_skill: dict = {}
    for p in current:
        per_skill[p["expected"]] = per_skill.get(p["expected"], 0) + 1
    for item in incoming[:limit]:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"), "a prompt")
        expected = item.get("expected") if isinstance(item.get("expected"), str) else None
        if expected is not None:
            validate_skill_name(expected)
        if (text, expected) in seen or per_skill.get(expected, 0) >= MAX_SAVED_PER_SKILL:
            continue
        seen.add((text, expected))
        per_skill[expected] = per_skill.get(expected, 0) + 1
        current.append({"text": text, "expected": expected})
    return current[:MAX_SAVED]


def save_prompt_set(data_dir: Path, payload: dict) -> dict:
    """Merge prompts or replace a scope's regression set with an optional precondition."""
    payload = payload if isinstance(payload, dict) else {}
    scope_id = payload.get("scope")
    path = _prompt_set_path(data_dir, scope_id)
    incoming = payload.get("prompts")
    if not isinstance(incoming, list):
        raise AiError("prompts must be a list", "ai-input")
    with mutation_lock(path):
        current = read_prompt_set(data_dir, scope_id)["prompts"]
        if "expected_prompts" in payload and payload["expected_prompts"] != current:
            raise AiError("the saved prompts changed; reload and try again", "ai-conflict", 409)
        replacing = bool(payload.get("replace"))
        current = _merge_prompts([] if replacing else current, incoming,
                                 MAX_SAVED if replacing else MAX_PROMPTS)
        mkdir_private(path.parent)
        atomic_write_text(path, json.dumps({"scope": scope_id, "prompts": current}, indent=1))
    return {"scope": scope_id, "prompts": current}


def _is_saved_run(result: dict) -> bool:
    return result.get("status") != "disconnected" and result.get("prompt_source") == "saved"


def _compare_with_previous(data_dir: Path, result: dict) -> tuple[str | None, list[dict]]:
    """Per-skill hit-rate change against the last saved-prompt run for this scope."""
    for row in list_runs(data_dir, limit=KEEP_RUNS):
        if row.get("kind") != "trigger-test" or row.get("scope") != result["scope"]:
            continue
        previous = read_run(data_dir, row["run_id"])
        if not _is_saved_run(previous):
            continue
        before = {s["name"]: s["hit_rate"] for s in previous.get("skills", [])}
        changes = []
        for skill in result["skills"]:
            old, new = before.get(skill["name"]), skill["hit_rate"]
            if old is not None and new is not None and old != new:
                changes.append({"name": skill["name"], "before": old, "after": new,
                                "regressed": new < old})
        return row["run_id"], sorted(changes, key=lambda c: (not c["regressed"], c["name"]))
    return None, []


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


def _run_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def _run_summary(path: Path) -> dict | None:
    try:
        data = _read_ai_json(path)
    except (OSError, ValueError, RecursionError, AiError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("run", {}), dict):
        return None
    return {"run_id": path.stem, "kind": data.get("kind"), "scope": data.get("scope"),
            "name": data.get("name"), "started": (data.get("run") or {}).get("started"),
            "model": (data.get("run") or {}).get("model"), "status": data.get("status")}


def list_runs(data_dir: Path, limit: int = 20) -> list[dict]:
    try:
        files = sorted(_runs_dir(data_dir).glob("*.json"), key=_run_mtime, reverse=True)
    except OSError:
        return []
    out = []
    for path in files:
        summary = _run_summary(path)
        if summary is not None:
            out.append(summary)
        if len(out) >= limit:
            break
    return out


def read_run(data_dir: Path, run_id: str) -> dict:
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-z-]+-\d{8}T\d{6}Z-[0-9a-f]{8}", run_id):
        raise AiError("unknown run id", "ai-input")
    path = _runs_dir(data_dir) / f"{run_id}.json"
    try:
        return _read_ai_json(path)
    except FileNotFoundError:
        raise AiError("that run no longer exists", "ai-not-found", 404) from None
    except (OSError, ValueError, RecursionError):
        raise AiError("that run file cannot be read", "ai-input") from None


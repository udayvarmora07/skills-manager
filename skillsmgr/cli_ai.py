"""A14 CLI: advisory trigger evidence and conservative CI comparisons."""
from __future__ import annotations

from . import ai_skills
from .ai import AiError
from .cli_output import err, print_json, sanitize_text


def validate_args(parser, args):
    if getattr(args, "fail_on_regression", False) and not getattr(args, "run", False):
        parser.error("--fail-on-regression requires --run")


def _baseline(data_dir, scope, run_id):
    if run_id:
        return run_id, ai_skills.read_run(data_dir, run_id)
    files = sorted(ai_skills._runs_dir(data_dir).glob("trigger-test-*.json"),
                   key=lambda path: (ai_skills._run_mtime(path), path.name), reverse=True)
    for path in files[:ai_skills.KEEP_RUNS]:
        previous = ai_skills.read_run(data_dir, path.stem)
        if previous.get("scope") == scope and previous.get("prompt_source") == "saved":
            return path.stem, previous
    return None, None


def _signature(result):
    provenance, run = result["provenance"], result["run"]
    return (result["scope"], result["seed"], result["repeats"], provenance["version"],
            provenance["router"], provenance["prompt_sha256"], provenance["endpoint_sha256"],
            run["provider"], run["model"])


def _listing_names(result):
    listing = result["listing_snapshot"]
    if not isinstance(listing, list) or not listing or len(listing) > ai_skills.MAX_LISTED:
        raise ValueError("invalid listing snapshot")
    names = set()
    for entry in listing:
        name, description = entry["name"], entry["description"]
        if not isinstance(name, str) or not isinstance(description, str) or name in names:
            raise ValueError("invalid listing entry")
        names.add(name)
    if ai_skills._fingerprint(listing) != result["provenance"]["listing_sha256"]:
        raise ValueError("listing fingerprint does not match evidence")
    return names


def _prompt_counts(row, names, repeats):
    expected, choices = row["expected"], row["choices"]
    if expected is not None and expected not in names:
        raise ValueError("expected skill absent from listing")
    if not isinstance(row["text"], str) or not row["text"]:
        raise ValueError("invalid prompt text")
    if not isinstance(choices, dict) or not choices:
        raise ValueError("missing choices")
    if type(row["answered"]) is not int or row["answered"] != repeats:
        raise ValueError("incomplete prompt")
    for choice, count in choices.items():
        if choice not in names | {ai_skills.NONE} or type(count) is not int or count < 1:
            raise ValueError("invalid choice count")
    if sum(choices.values()) != repeats:
        raise ValueError("inconsistent answer counts")
    return expected, choices.get(expected or ai_skills.NONE, 0)


def _metrics(result):
    """Recompute counts from complete observations instead of trusting rates."""
    if result["kind"] != "trigger-test" or result.get("status") not in (None, "complete"):
        raise ValueError("not a completed trigger test")
    if result["run"]["estimate_only"] is not False or result.get("prompt_source") != "saved":
        raise ValueError("not a saved-prompt measurement")
    for field in ("invalid_answers", "missing_answers"):
        if type(result[field]) is not int or result[field] != 0:
            raise ValueError("incomplete routing evidence")
    repeats = ai_skills._repeats(result["repeats"])
    ai_skills._trigger_seed(result["seed"])
    names = _listing_names(result)
    rows = result["prompts"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= ai_skills.MAX_PROMPTS:
        raise ValueError("missing prompt observations")
    metrics = {}
    for row in rows:
        expected, hits = _prompt_counts(row, names, repeats)
        metric = metrics.setdefault(expected, {"hits": 0, "answers": 0})
        metric["hits"] += hits
        metric["answers"] += repeats
    fingerprint = ai_skills._fingerprint([[p["text"], p["expected"]] for p in rows])
    if fingerprint != result["provenance"]["prompt_sha256"]:
        raise ValueError("prompt fingerprint does not match evidence")
    return metrics


def _validate_baseline(previous, current):
    try:
        if _signature(previous) != _signature(current):
            raise ValueError("prompts, scope, model, endpoint, seed or repeats differ")
        if previous["provenance"]["version"] != 1 or previous["provenance"]["router"] != "trigger-test-v1":
            raise ValueError("unsupported routing evidence version")
        return _metrics(previous)
    except (KeyError, TypeError, ValueError, AiError) as exc:
        raise AiError(f"baseline is not comparable: {exc}", "ai-baseline-incomparable") from None


def _compare(previous, result, run_id):
    if previous is None:
        return {"status": "missing", "baseline_run_id": None}
    try:
        before = _validate_baseline(previous, result)
    except AiError as exc:
        return {"status": "incomparable", "baseline_run_id": run_id, "reason": str(exc)}
    if result["run"]["estimate_only"]:
        return {"status": "not-run", "baseline_run_id": run_id}
    after = _metrics(result)
    metrics = [{"expected": name, "before": before[name], "after": counts,
                "regressed": counts["hits"] < before[name]["hits"]}
               for name, counts in sorted(after.items(), key=lambda item: item[0] or "~")]
    return {"status": "compared", "baseline_run_id": run_id, "metrics": metrics,
            "regressed": any(m["regressed"] for m in metrics),
            "listing_changed": previous["provenance"]["listing_sha256"] != result["provenance"]["listing_sha256"],
            "advisory": "An observed sample decrease; provider output varies. This is not a statistical significance test."}


def _execute(args, data_dir):
    payload = {"scope": args.scope, "saved": True, "strict_saved": True,
               "compare_previous": False, "repeats": args.repeats, "seed": args.seed,
               "estimate": not args.run}
    baseline_id, previous = _baseline(data_dir, args.scope, args.baseline)
    def preflight(result):
        if args.fail_on_regression:
            if previous is None:
                raise AiError("no saved baseline; run once without --fail-on-regression first", "ai-baseline-missing")
            _validate_baseline(previous, result)
    result = ai_skills.trigger_test(data_dir, payload, preflight=preflight)
    if args.run:
        try:
            _metrics(result)
        except (KeyError, TypeError, ValueError, AiError):
            return {"status": "incomplete", "result": result,
                    "comparison": {"status": "incomparable", "baseline_run_id": baseline_id}}, 1
    comparison = _compare(previous, result, baseline_id)
    failed = args.fail_on_regression and (comparison["status"] != "compared" or comparison.get("regressed"))
    status = "regression" if comparison.get("regressed") else "completed" if args.run else "estimate"
    if failed and comparison["status"] != "compared":
        status = "incomparable"
    return {"status": status, "result": result, "comparison": comparison}, int(bool(failed))


def _human_report(report):
    print("AI trigger test: " + sanitize_text(report["status"]))
    if "error" in report:
        err(sanitize_text(report["error"]["message"]))
        return
    result = report["result"]
    for line in result["egress"]:
        print(sanitize_text(line))
    print(sanitize_text(result["run"]["advisory"]))
    print(f"Model: {sanitize_text(result['run']['model'])}; seed: {result['seed']}; repeats: {result['repeats']}")
    print("Comparison: " + sanitize_text(report["comparison"]["status"]))
    if result.get("run_id"):
        print("Saved run: " + sanitize_text(result["run_id"]))


def cmd_ai(args, store) -> int:
    try:
        report, code = _execute(args, store.data_dir)
    except AiError as exc:
        report, code = {"status": "error", "error": {"code": exc.code, "message": str(exc)}}, 1
    except (OSError, ValueError, TypeError, RecursionError):
        report, code = {"status": "error", "error": {"code": "ai-input", "message": "cannot read AI input or run evidence; check saved files"}}, 1
    report = {"schema_version": 1, "command": "ai trigger-test", **report}
    if args.json:
        print_json(report)
    else:
        _human_report(report)
    return code

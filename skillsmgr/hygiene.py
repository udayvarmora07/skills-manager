"""Deterministic, read-only evidence for a skill hygiene report.

The filesystem remains the source of truth.  This module deliberately owns the
report policy so the CLI, REST endpoint, and Quality view consume one bounded
shape instead of implementing duplicate/similarity rules independently.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import loader, source_lock, validator
from .tokens import estimate


MAX_PAIRS = 100_000
MAX_NEAR_RESULTS = 500
MAX_FINDINGS = 2_000
MAX_GROUP_INSTANCES = 100
MAX_FEATURE_POSTING = 64
MAX_DESCRIPTION_CHARS = 1_024
MAX_HEADING_CHARS = 16_384
MAX_SHARED_FEATURES = 20
MAX_STRING = 512

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_CATEGORY_ORDER = (
    "missing-document",
    "unreadable-document",
    "document-conflict",
    "unaddressable",
    "validation",
    "broken-reference",
    "activation-description",
    "context-over-limit",
    "same-name-identical",
    "divergent-name",
    "exact-document-duplicate",
    "exact-instruction-duplicate",
    "near-duplicate",
    "source-lock-drift",
    "source-lock-inaccessible",
    "source-lock-evidence",
)
_CATEGORY_RANK = {value: index for index, value in enumerate(_CATEGORY_ORDER)}
_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2, "unavailable": 3}


class HygieneError(ValueError):
    """Raised when a hygiene report cannot be formed from its input."""


def _bounded(value: object, limit: int = MAX_STRING) -> str:
    text = value if isinstance(value, str) else str(value)
    text = text.replace("\x00", "�")
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _json_default(value: object) -> str:
    return _bounded(value)


def normalize_instruction_body(body: str) -> str:
    """Normalize only line endings, horizontal tails, and outer blank lines."""
    if not isinstance(body, str):
        raise HygieneError("instruction body must be text")
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def _identity(record: dict) -> str:
    value = record.get("physical_path") or record.get("path")
    if not value and isinstance(record.get("provenance"), dict):
        value = record["provenance"].get("path")
    if value:
        try:
            return str(Path(str(value)).expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            return _bounded(value)
    scope = _bounded(record.get("scope", ""), 128)
    name = _bounded(record.get("name", ""), 128)
    return f"<missing-path>/{scope}/{name}"


def _record_sort_key(record: dict) -> tuple[str, str, str, str]:
    return (
        str(record.get("name", "")).casefold(),
        str(record.get("scope", "")).casefold(),
        _identity(record),
        str(record.get("path", "")),
    )


def _deduplicate_physical_instances(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for original in records:
        if not isinstance(original, dict):
            continue
        grouped[_identity(original)].append(dict(original))
    result = []
    for physical in sorted(grouped):
        aliases = sorted(grouped[physical], key=_record_sort_key)
        # Prefer the observation with the richest body/hash/validation data,
        # using scope/path only as deterministic tie breakers.
        chosen = max(
            aliases,
            key=lambda item: (
                int(bool(item.get("body"))),
                int(bool(item.get("content_hash"))),
                int(bool(item.get("metadata_hash"))),
                int(bool(item.get("description"))),
                tuple(reversed(_record_sort_key(item))),
            ),
        )
        chosen["_aliases"] = [
            {
                "scope": alias.get("scope"),
                "scope_label": alias.get("scope_label"),
                "consumer": alias.get("consumer"),
            }
            for alias in aliases
        ]
        result.append(chosen)
    return sorted(result, key=_record_sort_key)


def _path(record: dict) -> Path | None:
    value = record.get("physical_path") or record.get("path")
    if not value:
        return None
    try:
        return Path(str(value)).expanduser()
    except (TypeError, ValueError):
        return None


def _read_observation(record: dict, degraded: list[dict]) -> None:
    """Fill missing live fields from one already-observed skill directory."""
    path = _path(record)
    if path is None or ("body" in record and "content_hash" in record):
        return
    try:
        if not path.exists():
            degraded.append({
                "instance": _bounded(_identity(record)),
                "section": "filesystem-observation",
                "reason": "observed skill path disappeared before hygiene analysis",
                "truncated": False,
            })
            record["document_missing"] = True
            record["_filesystem_unavailable"] = True
            return
    except OSError as exc:
        degraded.append({
            "instance": _bounded(_identity(record)),
            "section": "filesystem-observation",
            "reason": _bounded(str(exc)),
        })
        record["_filesystem_unavailable"] = True
        return
    try:
        observed = loader.load_skill(path, include_husks=True)
    except Exception as exc:  # a single disappearing/readable entry is bounded
        degraded.append({
            "instance": _bounded(_identity(record)),
            "section": "filesystem-observation",
            "reason": _bounded(str(exc)),
        })
        record.setdefault("malformed", True)
        record.setdefault("decode_error", _bounded(str(exc)))
        record["_filesystem_unavailable"] = True
        return
    for key in (
        "body", "description", "content_hash", "metadata_hash", "tokens",
        "tokens_method", "tokens_pct", "chars", "malformed", "document_missing",
        "document_conflict", "decode_error", "addressable", "disabled", "version",
        "portable_frontmatter", "frontmatter_extensions",
    ):
        if key in observed and key not in record:
            record[key] = observed[key]


def _issue_dict(issue: object) -> dict:
    if isinstance(issue, dict):
        return {
            "level": _bounded(issue.get("level", "warning"), 32),
            "key": _bounded(issue.get("key", ""), 128),
            "message": _bounded(issue.get("message", "")),
        }
    return {
        "level": _bounded(getattr(issue, "level", "warning"), 32),
        "key": _bounded(getattr(issue, "key", ""), 128),
        "message": _bounded(getattr(issue, "message", str(issue))),
    }


def _validate_record(record: dict, degraded: list[dict]) -> list[dict]:
    supplied = record.get("validation")
    if supplied is not None:
        raw = supplied.get("issues", []) if isinstance(supplied, dict) else getattr(supplied, "issues", [])
        return [_issue_dict(issue) for issue in raw]
    path = _path(record)
    if path is None or record.get("addressable") is False or record.get("document_missing") or record.get("link_escape"):
        return []
    try:
        result = validator.validate_skill(str(record.get("name", path.name)), path)
        return [_issue_dict(issue) for issue in result.issues]
    except Exception as exc:
        degraded.append({
            "instance": _bounded(_identity(record)),
            "section": "validation",
            "reason": _bounded(str(exc)),
        })
        return []


def _prepare_records(records: list[dict], max_instances: int) -> tuple[list[dict], list[dict]]:
    if not isinstance(records, list):
        raise HygieneError("records must be a list")
    if isinstance(max_instances, bool) or not isinstance(max_instances, int) or max_instances < 1:
        raise HygieneError("max_instances must be a positive integer")
    degraded: list[dict] = []
    prepared = _deduplicate_physical_instances(records)
    if len(prepared) > max_instances:
        omitted = prepared[max_instances:]
        prepared = prepared[:max_instances]
        degraded.append({
            "section": "physical-instances",
            "reason": f"physical-instance limit reached at {max_instances}; omitted {len(omitted)} instances",
            "truncated": True,
        })
    for record in prepared:
        _read_observation(record, degraded)
        record["_issues"] = _validate_record(record, degraded)
        body = record.get("body")
        if not isinstance(body, str):
            record["body"] = ""
        record["_instruction_body"] = normalize_instruction_body(record["body"])
    return prepared, degraded


def _public_instance(record: dict) -> dict:
    result = {
        "name": _bounded(record.get("name", ""), 128),
        "scope": _bounded(record.get("scope", ""), 128),
        "scope_label": _bounded(record.get("scope_label", record.get("scope", "")), 128),
        "consumer": _bounded(record.get("consumer", ""), 128),
        "disabled": bool(record.get("disabled")),
        "addressable": record.get("addressable") is not False,
        "malformed": bool(record.get("malformed")),
        "content_hash": _bounded(record.get("content_hash", ""), 128),
        "metadata_hash": _bounded(record.get("metadata_hash", ""), 128),
        "tokens": int(record.get("tokens", 0) or 0),
        "tokens_method": _bounded(record.get("tokens_method", "unavailable"), 64),
    }
    path = record.get("physical_path") or record.get("path")
    if path:
        result["physical_path"] = _bounded(path, MAX_STRING)
    else:
        result["path"] = "path unavailable"
    return result


def _public_observation(record: dict) -> dict:
    result = _public_instance(record)
    for key in ("chars", "lines"):
        if key in record:
            result[key] = int(record.get(key, 0) or 0)
    if "chars" not in result and isinstance(record.get("body"), str):
        result["chars"] = len(record["body"])
    return result


def _stable_finding_id(category: str, records: list[dict]) -> str:
    identities = sorted(_identity(record) for record in records)
    payload = json.dumps(
        {"category": category, "instances": identities},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _finding(
    category: str,
    severity: str,
    confidence: str,
    title: str,
    explanation: str,
    records: list[dict],
    evidence: dict,
    recommendation: str,
) -> dict:
    ordered = sorted(records, key=_record_sort_key)
    shown = ordered[:MAX_GROUP_INSTANCES]
    safe_evidence = json.loads(json.dumps(evidence, ensure_ascii=False, default=_json_default))
    if len(ordered) > MAX_GROUP_INSTANCES:
        safe_evidence["instances_truncated"] = True
        safe_evidence["instances_total"] = len(ordered)
    return {
        "id": _stable_finding_id(category, ordered),
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "title": _bounded(title),
        "explanation": _bounded(explanation),
        "evidence": safe_evidence,
        "instances": [_public_instance(record) for record in shown],
        "recommendation": _bounded(recommendation),
        "automatic_action": False,
    }


def _validation_findings(records: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        issues = record.get("_issues", [])
        structural = []
        if record.get("document_missing"):
            findings.append(_finding(
                "missing-document", "error", "observed",
                f"{record.get('name', '')} has no skill document",
                "The observed skill directory has neither SKILL.md nor SKILL.md.disabled.",
                [record], {"document_missing": True},
                "Inspect the exact physical directory and restore one primary document deliberately.",
            ))
        if record.get("decode_error"):
            findings.append(_finding(
                "unreadable-document", "error", "observed",
                f"{record.get('name', '')} cannot be read as a clean document",
                "The primary document is unreadable, non-UTF-8, or otherwise carries a loader read error.",
                [record], {"message": _bounded(record["decode_error"])},
                "Inspect the exact physical document and re-save it as valid UTF-8 if appropriate.",
            ))
        if record.get("document_conflict"):
            findings.append(_finding(
                "document-conflict", "error", "observed",
                f"{record.get('name', '')} has conflicting documents",
                "Both SKILL.md and SKILL.md.disabled are present, so the active document is ambiguous.",
                [record], {"document_conflict": True},
                "Inspect both documents and remove the ambiguity manually before toggling the skill.",
            ))
        if record.get("link_escape"):
            structural.append({"level": "error", "key": "path", "message": _bounded(record.get("decode_error", "skill path escapes its scope"))})
        if record.get("addressable") is False:
            findings.append(_finding(
                "unaddressable", "warning", "observed",
                f"{record.get('name', '')} cannot be addressed by name",
                "The directory is readable but its name does not satisfy the manager's canonical skill-name rule.",
                [record], {"addressable": False},
                "Inspect the physical path and rename it deliberately if it should be managed here.",
            ))
        structural.extend(
            issue for issue in issues
            if issue.get("level") == "error"
            and issue.get("message") != _bounded(record.get("decode_error", ""))
        )
        if record.get("malformed") and not structural and not record.get("document_conflict"):
            structural.append({"level": "error", "key": "document", "message": "loader marked the document malformed"})
        if structural:
            findings.append(_finding(
                "validation", "error", "observed",
                f"{record.get('name', '')} has validation errors",
                "The existing validator reported one or more error-level issues for this physical instance.",
                [record], {"issues": _unique_issues(structural)},
                "Open Validate for the exact instance and resolve the reported specification or filesystem issues deliberately.",
            ))
    return findings


def _unique_issues(issues: list[dict]) -> list[dict]:
    unique = {(item.get("level"), item.get("key"), item.get("message")): item for item in issues}
    return [unique[key] for key in sorted(unique)]


def _groups(records: list[dict], key_name: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        key = record.get(key_name)
        if key:
            groups[str(key)].append(record)
    return groups


def _duplicate_findings(records: list[dict]) -> list[dict]:
    findings = []
    by_name: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_name[str(record.get("name", ""))].append(record)
    for name in sorted(by_name, key=str.casefold):
        group = by_name[name]
        hashes = {record.get("content_hash") for record in group if record.get("content_hash")}
        for content_hash in sorted(hashes):
            identical = [item for item in group if item.get("content_hash") == content_hash]
            if len(identical) < 2:
                continue
            findings.append(_finding(
                "same-name-identical", "info", "observed",
                f"{name} is identical across {len(identical)} physical copies",
                "Distinct physical instances with the same observed name have the same complete primary-document hash.",
                identical, {"content_hash": content_hash},
                "Inspect the exact copies and retain or converge them deliberately; no winner is selected.",
            ))
        if len(hashes) > 1:
            findings.append(_finding(
                "divergent-name", "warning", "observed",
                f"{name} differs across {len(group)} physical copies",
                "The observed primary-document hashes are not equal; consumer precedence and effective load are not inferred.",
                group, {
                    "content_hashes": sorted(hashes),
                    "disabled_states": sorted({bool(item.get("disabled")) for item in group}),
                    "versions": sorted({_bounded(item.get("version", "")) for item in group}),
                    "descriptions": sorted({_bounded(item.get("description", "")) for item in group}),
                    "metadata_hashes": sorted({item.get("metadata_hash", "") for item in group}),
                    "tokens": sorted({int(item.get("tokens", 0) or 0) for item in group}),
                    "effective_load": "not inferred",
                },
                "Inspect both exact instances and use the existing diff/update or sync workflow deliberately.",
            ))
    by_hash = _groups(records, "content_hash")
    for content_hash in sorted(by_hash):
        group = by_hash[content_hash]
        names = {str(item.get("name", "")) for item in group}
        if len(group) > 1 and len(names) > 1:
            findings.append(_finding(
                "exact-document-duplicate", "info", "observed",
                f"{len(group)} differently named copies share one document",
                "Distinct physical instances with different observed names have the same complete primary-document hash.",
                group, {"content_hash": content_hash, "names": sorted(names)},
                "Inspect every exact instance before deciding whether the names represent intentional aliases.",
            ))
    by_body: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        body = record.get("_instruction_body", "")
        if body:
            by_body[hashlib.sha256(body.encode("utf-8")).hexdigest()].append(record)
    for body_hash in sorted(by_body):
        group = by_body[body_hash]
        names = {str(item.get("name", "")) for item in group}
        documents = {item.get("content_hash") for item in group if item.get("content_hash")}
        if len(group) > 1 and len(names) > 1 and len(documents) > 1:
            findings.append(_finding(
                "exact-instruction-duplicate", "info", "observed",
                f"{len(group)} differently named copies share one instruction body",
                "Non-empty instruction bodies match after only line-ending, trailing-space, and outer-blank-line normalization.",
                group, {"instruction_hash": body_hash, "names": sorted(names)},
                "Inspect the exact instances and compare their frontmatter before deliberately converging them.",
            ))
    return findings


def _normalized_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return set(token for token in _TOKEN_RE.findall(normalized) if len(token) >= 2)


def _features(record: dict) -> dict[str, set[str]]:
    name = unicodedata.normalize("NFKC", str(record.get("name", ""))).casefold()
    name = name.replace("_", " ").replace(".", " ").replace("-", " ")
    joined = "".join(name.split())
    trigrams = {joined[index:index + 3] for index in range(max(0, len(joined) - 2))}
    description = str(record.get("description", ""))[:MAX_DESCRIPTION_CHARS]
    body = str(record.get("body", ""))[:MAX_HEADING_CHARS]
    headings = " ".join(_HEADING_RE.findall(body))
    return {
        "name": _normalized_tokens(name) | {f"#{item}" for item in trigrams},
        "description": _normalized_tokens(description),
        "heading": _normalized_tokens(headings),
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _candidate_pairs(features: list[dict], max_pairs: int) -> tuple[list[tuple[int, int]], bool]:
    indexes = {"name": defaultdict(list), "description": defaultdict(list)}
    for index, feature in enumerate(features):
        for key in indexes:
            for value in sorted(feature[key]):
                indexes[key][value].append(index)
    candidates: set[tuple[int, int]] = set()
    truncated = False
    for key in ("name", "description"):
        for value in sorted(indexes[key]):
            posting = indexes[key][value]
            if len(posting) > MAX_FEATURE_POSTING:
                continue
            for left_offset, left in enumerate(posting):
                for right in posting[left_offset + 1:]:
                    pair = (left, right)
                    if pair in candidates:
                        continue
                    if len(candidates) >= max_pairs:
                        truncated = True
                        return sorted(candidates), truncated
                    candidates.add(pair)
    return sorted(candidates), truncated


def near_duplicate_candidates(
    records: list[dict], *, max_pairs: int = MAX_PAIRS, max_results: int = MAX_NEAR_RESULTS
) -> dict:
    """Return bounded, explainable near-duplicate candidates."""
    if isinstance(max_pairs, bool) or not isinstance(max_pairs, int) or max_pairs < 1:
        raise HygieneError("max_pairs must be a positive integer")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
        raise HygieneError("max_results must be a positive integer")
    ordered = sorted((dict(record) for record in records if isinstance(record, dict)), key=_record_sort_key)
    features = [_features(record) for record in ordered]
    pairs, candidate_truncated = _candidate_pairs(features, max_pairs)
    results = []
    for left_index, right_index in pairs:
        left = ordered[left_index]
        right = ordered[right_index]
        if str(left.get("name", "")) == str(right.get("name", "")):
            continue
        if left.get("content_hash") and left.get("content_hash") == right.get("content_hash"):
            continue
        left_body = left.get("_instruction_body") or normalize_instruction_body(str(left.get("body", "")))
        right_body = right.get("_instruction_body") or normalize_instruction_body(str(right.get("body", "")))
        if (
            not left_body
            or not right_body
            or left.get("decode_error")
            or right.get("decode_error")
            or left.get("document_missing")
            or right.get("document_missing")
            or left.get("_filesystem_unavailable")
            or right.get("_filesystem_unavailable")
        ):
            continue
        if left_body == right_body:
            continue
        left_features, right_features = features[left_index], features[right_index]
        shared_names = left_features["name"] & right_features["name"]
        shared_descriptions = left_features["description"] & right_features["description"]
        if not shared_names and len(shared_descriptions) < 2:
            continue
        name_score = _jaccard(left_features["name"], right_features["name"])
        description_score = _jaccard(left_features["description"], right_features["description"])
        heading_score = _jaccard(left_features["heading"], right_features["heading"])
        similarity = 0.50 * name_score + 0.35 * description_score + 0.15 * heading_score
        if similarity < 0.78 or (name_score < 0.50 and description_score < 0.80):
            continue
        results.append({
            "records": [left, right],
            "similarity": round(similarity, 4),
            "name_similarity": round(name_score, 4),
            "description_similarity": round(description_score, 4),
            "heading_similarity": round(heading_score, 4),
            "shared_name_features": sorted(shared_names)[:MAX_SHARED_FEATURES],
            "shared_description_tokens": sorted(shared_descriptions)[:MAX_SHARED_FEATURES],
            "reason": "shared normalized name features or description tokens exceed the documented heuristic threshold",
        })
    results.sort(key=lambda item: (-item["similarity"], _identity(item["records"][0]), _identity(item["records"][1])))
    result_truncated = len(results) > max_results
    return {
        "candidates": results[:max_results],
        "candidate_pairs_scored": len(pairs),
        "candidate_pairs_truncated": candidate_truncated,
        "results_truncated": result_truncated,
        "degraded": ([{"section": "near-duplicate", "reason": "candidate pair cap reached", "truncated": True}] if candidate_truncated else [])
        + ([{"section": "near-duplicate", "reason": "result cap reached", "truncated": True}] if result_truncated else []),
    }


def _reference_kind(message: str) -> str | None:
    text = message.lower()
    if "body mentions" in text and "does not exist" in text:
        return "missing-layout"
    if "escapes the skill directory" in text:
        return "out-of-root"
    if "cannot be resolved" in text:
        return "unresolvable"
    if "does not exist" in text:
        return "missing"
    return None


def _reference_findings(records: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        issues = []
        seen = set()
        for issue in record.get("_issues", []):
            kind = _reference_kind(issue.get("message", ""))
            if kind is None:
                continue
            key = (kind, issue.get("level"), issue.get("key"), issue.get("message"))
            if key in seen:
                continue
            seen.add(key)
            issues.append({"kind": kind, **issue})
        if not issues:
            continue
        severity = "error" if any(item.get("level") == "error" for item in issues) else "warning"
        findings.append(_finding(
            "broken-reference", severity, "observed",
            f"{record.get('name', '')} has broken references",
            "The existing validator reported missing, unresolvable, out-of-root, or missing-layout targets.",
            [record], {"issues": sorted(issues, key=lambda item: (item["kind"], item.get("message", "")))},
            "Open Validate for the exact addressable instance and inspect the referenced target deliberately.",
        ))
    return findings


def _description_findings(records: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        description = record.get("description", "")
        if not isinstance(description, str):
            description = ""
        score = validator.description_score(description)
        messages = [
            issue for issue in record.get("_issues", [])
            if issue.get("key") == "description"
        ]
        short = bool(description.strip()) and len(description) < 20
        if description.strip() and score["has_use_context"] and not score["filler_hits"] and not short and not messages:
            continue
        if not description.strip() and not messages:
            messages = [{"level": "error", "key": "description", "message": "description is missing or empty"}]
        severity = "error" if any(item.get("level") == "error" for item in messages) else "warning"
        findings.append(_finding(
            "activation-description", severity, "observed",
            f"{record.get('name', '')} has activation-description evidence",
            "The existing description guidance reports missing context, vague filler, invalid content, or a short description.",
            [record], {
                "has_use_context": bool(score["has_use_context"]),
                "filler_hits": sorted(score["filler_hits"]),
                "word_count": int(score["word_count"]),
                "validator_messages": messages,
            },
            "Open Validate for the exact instance and make the description concrete about what and when it helps.",
        ))
    return findings


def _context_findings(records: list[dict]) -> tuple[list[dict], list[dict]]:
    findings = []
    largest = []
    for record in records:
        body = record.get("body", "") if isinstance(record.get("body", ""), str) else ""
        body_estimate = estimate(body)
        body_tokens = int(record.get("body_tokens", body_estimate["tokens"]) or 0)
        body_lines = len(body.splitlines())
        over_tokens = body_tokens > validator.MAX_BODY_TOKENS
        over_lines = body_lines > validator.MAX_BODY_LINES
        validator_issues = [
            issue for issue in record.get("_issues", [])
            if issue.get("key") == "body" and (
                "tokens" in issue.get("message", "") or "lines" in issue.get("message", "")
            )
        ]
        if over_tokens or over_lines or validator_issues:
            findings.append(_finding(
                "context-over-limit", "warning", "observed",
                f"{record.get('name', '')} exceeds a documented body limit",
                "The validator's existing progressive-disclosure thresholds identify unusually large body context.",
                [record], {
                    "body_tokens": body_tokens,
                    "body_lines": body_lines,
                    "max_body_tokens": validator.MAX_BODY_TOKENS,
                    "max_body_lines": validator.MAX_BODY_LINES,
                    "validator_messages": validator_issues,
                },
                "Open Validate and consider moving reference material into bounded progressive-disclosure files.",
            ))
        item = _public_observation(record)
        item["body_tokens"] = body_tokens
        item["body_lines"] = body_lines
        largest.append(item)
    largest.sort(key=lambda item: (-int(item.get("tokens", 0)), str(item.get("name", "")).casefold(), str(item.get("physical_path", item.get("path", "")))))
    return findings, largest[:20]


def _source_lock_findings(records: list[dict], unavailable: list[dict], degraded: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        path = _path(record)
        if path is None or record.get("addressable") is False:
            continue
        try:
            status = source_lock.source_lock_status(path)
        except Exception as exc:
            degraded.append({"instance": _bounded(_identity(record)), "section": "source-lock", "reason": _bounded(str(exc))})
            status = {"state": "inaccessible", "error": str(exc)}
        state = status.get("state", "inaccessible")
        if state == "missing":
            unavailable.append({
                "signal": "source-lock",
                "scope": record.get("scope", ""),
                "name": record.get("name", ""),
                "state": "missing",
                "explanation": "No source-lock sidecar is recorded for this physical instance; freshness and provenance are not observed.",
            })
            continue
        if state == "changed":
            findings.append(_finding(
                "source-lock-drift", "warning", "observed",
                f"{record.get('name', '')} differs from its source lock",
                "The installed tree differs from the recorded source-lock content hash.",
                [record], {"state": state, "content_hash": status.get("content_hash")},
                "Inspect the exact source/update review before applying any deliberate change.",
            ))
            continue
        if state == "inaccessible":
            findings.append(_finding(
                "source-lock-inaccessible", "warning", "observed",
                f"{record.get('name', '')} source evidence is inaccessible",
                "The source-lock sidecar or current tree could not be safely read or manifested.",
                [record], {"state": state, "error": _bounded(status.get("error", "source evidence unavailable"))},
                "Inspect the exact physical directory and source-lock sidecar permissions manually.",
            ))
            continue
        findings.append(_finding(
            "source-lock-evidence", "info", "observed",
            f"{record.get('name', '')} has source-lock evidence",
            "A source identity and recorded content hash are present; this is evidence, not a safety or trust verdict.",
            [record], {
                "state": state,
                "content_hash": status.get("content_hash"),
                "recorded_content_hash": (status.get("lock") or {}).get("content_hash") if isinstance(status.get("lock"), dict) else None,
                "checked_at": (status.get("lock") or {}).get("checked_at") if isinstance(status.get("lock"), dict) else None,
                "source": _safe_source(status.get("lock")),
            },
            "Use the existing source/update review surface when inspecting this exact instance.",
        ))
    return findings


def _safe_source(lock: object) -> dict:
    if not isinstance(lock, dict):
        return {}
    source = lock.get("source")
    if not isinstance(source, dict):
        return {}
    return {
        key: _bounded(source[key])
        for key in ("kind", "value", "revision", "digest")
        if source.get(key) is not None
    }


def _unavailable_signals() -> list[dict]:
    return [
        {"signal": "invocation-usage", "explanation": "Invocation count and last-used time are not recorded by the manager."},
        {"signal": "unused-by-usage", "explanation": "Unused or stale-by-usage status cannot be inferred without invocation evidence."},
        {"signal": "remote-freshness", "explanation": "Remote freshness and available-update evidence are not part of this read-only scan."},
        {"signal": "publisher-trust", "explanation": "Publisher identity, signatures, and trust are not established by this report."},
        {"signal": "semantic-usefulness", "explanation": "Semantic correctness and usefulness are not observable from these filesystem records."},
        {"signal": "effective-load", "explanation": "Precedence-resolved effective load for arbitrary consumers is not inferred."},
        {"signal": "external-readiness", "explanation": "External binaries, credentials, MCPs, and runtime readiness are not checked."},
    ]


def _finding_sort_key(finding: dict) -> tuple[int, int, str, str]:
    return (
        _SEVERITY_RANK.get(finding.get("severity"), 99),
        _CATEGORY_RANK.get(finding.get("category"), 99),
        str(finding.get("title", "")).casefold(),
        str(finding.get("id", "")),
    )


def _summary(findings: list[dict], observed_records: int, physical_count: int, logical_count: int) -> dict:
    counts = defaultdict(int)
    categories = defaultdict(int)
    for finding in findings:
        counts[finding.get("severity", "info")] += 1
        categories[finding.get("category", "unknown")] += 1
    return {
        "observed_records": observed_records,
        "physical_instances": physical_count,
        "logical_names": logical_count,
        "errors": counts["error"],
        "warnings": counts["warning"],
        "informational": counts["info"],
        "unavailable": counts["unavailable"],
        "finding_count": len(findings),
        "findings_returned": min(len(findings), MAX_FINDINGS),
        "findings_truncated": len(findings) > MAX_FINDINGS,
        "partial": False,
        "category_counts": dict(sorted(categories.items())),
    }


def hygiene_report(records: list[dict], *, scope: str, max_instances: int = 10_000) -> dict:
    """Build a stable JSON-safe read-only hygiene report."""
    prepared, degraded = _prepare_records(records, max_instances)
    unavailable = _unavailable_signals()
    findings = _validation_findings(prepared)
    findings.extend(_duplicate_findings(prepared))
    near = near_duplicate_candidates(prepared)
    for item in near["candidates"]:
        pair = item["records"]
        findings.append(_finding(
            "near-duplicate", "info", "heuristic",
            f"{pair[0].get('name', '')} and {pair[1].get('name', '')} may overlap",
            "Differently named readable instances passed the bounded local text-feature heuristic; this is not a confirmed duplicate.",
            pair, {
                "similarity": item["similarity"],
                "name_similarity": item["name_similarity"],
                "description_similarity": item["description_similarity"],
                "heading_similarity": item["heading_similarity"],
                "shared_name_features": item["shared_name_features"],
                "shared_description_tokens": item["shared_description_tokens"],
                "reason": item["reason"],
            },
            "Inspect both exact instances; similarity is advisory and no cleanup action is proposed.",
        ))
    degraded.extend(near.get("degraded", []))
    findings.extend(_reference_findings(prepared))
    findings.extend(_description_findings(prepared))
    context_findings, largest = _context_findings(prepared)
    findings.extend(context_findings)
    findings.extend(_source_lock_findings(prepared, unavailable, degraded))
    findings.sort(key=_finding_sort_key)
    full_summary = _summary(findings, len(records), len(prepared), len({str(r.get("name", "")) for r in prepared}))
    full_summary["unavailable"] += len(unavailable)
    full_summary["partial"] = bool(degraded)
    category_counts = full_summary.pop("category_counts")
    result = {
        "version": 1,
        "scope": _bounded(scope, 128),
        "policy": "read-only evidence; no combined score or automatic cleanup",
        "summary": full_summary,
        "category_counts": category_counts,
        "findings": findings[:MAX_FINDINGS],
        "largest_instances": largest,
        "unavailable_signals": sorted(unavailable, key=lambda item: (str(item.get("signal", "")), str(item.get("name", "")))),
        "degraded": sorted(degraded, key=lambda item: (str(item.get("section", "")), str(item.get("instance", "")), str(item.get("reason", "")))),
        "limits": {
            "max_instances": max_instances,
            "max_candidate_pairs": MAX_PAIRS,
            "max_near_duplicate_findings": MAX_NEAR_RESULTS,
            "max_findings": MAX_FINDINGS,
            "max_group_instances": MAX_GROUP_INSTANCES,
            "max_feature_posting": MAX_FEATURE_POSTING,
            "max_description_characters": MAX_DESCRIPTION_CHARS,
            "max_heading_characters": MAX_HEADING_CHARS,
            "max_shared_features": MAX_SHARED_FEATURES,
            "max_string": MAX_STRING,
        },
    }
    return result


__all__ = [
    "HygieneError",
    "normalize_instruction_body",
    "near_duplicate_candidates",
    "hygiene_report",
]

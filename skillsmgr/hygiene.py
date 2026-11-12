"""Deterministic, read-only evidence for a skill hygiene report.

The filesystem remains the source of truth.  This module deliberately owns the
report policy so the CLI, REST endpoint, and Quality view consume one bounded
shape instead of implementing duplicate/similarity rules independently.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import key_support, loader, lockfiles, native_state, paths, source_lock, validator
from .lockfiles import MAX_STRING, bounded_text as _bounded
from .tokens import DEFAULT_WINDOW, WINDOWS, count_tokens, estimate, window_name


MAX_PAIRS = 100_000
MAX_NEAR_RESULTS = 500
MAX_FINDINGS = 2_000
MAX_GROUP_INSTANCES = 100
MAX_FEATURE_POSTING = 64
MAX_HEADING_CHARS = 16_384
MAX_SHARED_FEATURES = 20
MAX_LISTING_CANDIDATES = 25
MAX_LISTING_OVER_CAP = 50
#: docs/29 H2: at most this many agents-only names are listed in the bridge
#: section; the rest are counted as ``omitted``.
MAX_BRIDGE_NAMES = 50

#: Claude Code scope ids.  ``claude-code`` is the personal ``~/.claude/skills``
#: root; a project ``.claude/skills`` root is the ``project-claude`` facade id.
_CLAUDE_PERSONAL_SCOPE = "claude-code"
_CLAUDE_PROJECT_SCOPE = "project-claude"
_CLAUDE_LISTING_SOURCE = "https://code.claude.com/docs/en/skills"
_LISTING_SEPARATOR = "\n"
LISTING_CHARS_PER_TOKEN = 4
LISTING_ESTIMATE_ASSUMPTION = (
    "4 characters per token; the documented budget is in characters but scales "
    "from a token window and the conversion is not documented"
)
LISTING_TEXT_BASIS = (
    "'<name>: <description>' per entry, joined by one newline; the documented "
    "listing serialization is not published"
)
LISTING_CANDIDATE_WORDING = (
    "Candidates by size only. Claude Code drops descriptions starting with the "
    "least-invoked skills, which this tool cannot observe, so it cannot say "
    "which descriptions are actually dropped."
)

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
    "ignored-frontmatter",
    "context-over-limit",
    "claude-listing-budget",
    "agents-bridge-gap",
    "same-name-identical",
    "divergent-name",
    "exact-document-duplicate",
    "exact-instruction-duplicate",
    "near-duplicate",
    "source-lock-drift",
    "source-lock-inaccessible",
    "source-lock-unbound",
    "source-lock-evidence",
)
_CATEGORY_RANK = {value: index for index, value in enumerate(_CATEGORY_ORDER)}
_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2, "unavailable": 3}


class HygieneError(ValueError):
    """Raised when a hygiene report cannot be formed from its input."""


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


# Per-report memo of resolved instance paths.  ``_identity`` is the sort key
# of most orderings in this module, so one report resolved the same ~1,760
# paths about 16,000 times (one ``realpath`` walk each, ~1.9 s of a 7 s
# report).  The memo lives only for one ``hygiene_report`` call -- it is never
# a cache across requests, so a symlink changed between two reports is seen by
# the second one.  Outside a report (``None``) every call resolves afresh.
_RESOLVED_IDENTITIES: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "hygiene_resolved_identities", default=None
)


def _resolve_identity(value) -> str:
    try:
        return str(Path(str(value)).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return _bounded(value)


def _memoized_identity(value) -> str:
    memo = _RESOLVED_IDENTITIES.get()
    if memo is None:
        return _resolve_identity(value)
    key = str(value)
    if key not in memo:
        memo[key] = _resolve_identity(value)
    return memo[key]


def _identity(record: dict) -> str:
    value = record.get("physical_path") or record.get("path")
    if not value and isinstance(record.get("provenance"), dict):
        value = record["provenance"].get("path")
    if value:
        return _memoized_identity(value)
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
        chosen["_aliases"] = [_alias_observation(alias) for alias in aliases]
        result.append(chosen)
    return sorted(result, key=_record_sort_key)


def _alias_observation(alias: dict) -> dict:
    result = {key: _bounded(alias.get(key) or "") for key in ("scope", "scope_label", "consumer")}
    result["path"] = _bounded(alias.get("path", alias.get("physical_path")) or "")
    for key in ("disabled", "addressable", "malformed"):
        if key in alias:
            result[key] = bool(alias[key])
    if "instance_state" in alias:
        result["instance_state"] = _bounded(alias["instance_state"])
    return result


def _path(record: dict) -> Path | None:
    value = record.get("physical_path") or record.get("path")
    if not value:
        return None
    try:
        return Path(str(value)).expanduser()
    except (TypeError, ValueError):
        return None


def _read_observation(record: dict, degraded: list[dict], *, reuse: bool = True) -> None:
    """Fill missing live fields from one already-observed skill directory.

    ``reuse`` is forwarded to :func:`loader.load_skill`'s bounded derived-record
    reuse.  The caller measures it once for the whole batch, because a scan
    holding more documents than the cache can retain evicts every entry before
    the next pass reaches it -- see :func:`loader.document_reuse_worthwhile`.
    """
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
        observed = loader.load_skill(path, include_husks=True, reuse=reuse)
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
    # Measured AFTER the truncation above: this is the number of documents
    # actually loaded, not ``len(records)``.  ``hygiene_report`` defaults
    # ``max_instances`` to 10,000 and the reuse cache holds 4,096, so a scan
    # above the bound would evict every entry before the next pass reached it
    # and pay the bookkeeping for zero reuse -- a regression strictly worse
    # than having no cache at all.  Measured at 5,000 documents through a
    # 1,000-entry bound the second pass re-derived 5,001.
    reuse = loader.document_reuse_worthwhile(len(prepared))
    for record in prepared:
        _read_observation(record, degraded, reuse=reuse)
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
    result.update(_public_aliases(record))
    return result


def _public_aliases(record: dict) -> dict:
    aliases = record.get("_aliases", [])
    if len(aliases) <= 1:
        return {}
    result = {"observations": aliases[:MAX_GROUP_INSTANCES]}
    if len(aliases) > MAX_GROUP_INSTANCES:
        result["observations_total"] = len(aliases)
        result["observations_truncated"] = True
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


def _parse_risk_findings(records: list[dict]) -> list[dict]:
    """Validator warnings for frontmatter an agent's parser silently drops."""
    findings = []
    for record in records:
        issues = [issue for issue in record.get("_issues", [])
                  if issue.get("message") in validator.SILENT_FAILURE_MESSAGES]
        if issues:
            findings.append(_finding(
                "agent-parse-risk", "warning", "observed",
                f"{record.get('name', '')} may be skipped by an agent's frontmatter parser",
                "This tool reads the document, but a stricter agent parser drops frontmatter like this, "
                "so the skill can load with no name or description or not at all.",
                [record], {"issues": _unique_issues(issues)},
                "Fix the frontmatter as each message says, then validate the exact instance again.",
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
    description = str(record.get("description", ""))[:validator.MAX_DESCRIPTION]
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


#: Scopes whose reading consumer(s) have a documented frontmatter key list in
#: ``key_support``.  ``agents`` is the shared ``~/.agents/skills`` root read by
#: these six consumers per docs/34.
_KEY_SCOPE_CONSUMERS = {
    "claude-code": ("claude-code",),
    "codex": ("codex",),
    "gemini": ("gemini",),
    "opencode": ("opencode",),
    "agents": ("codex", "gemini", "opencode", "amp", "roo", "zed"),
}
#: Bounds the unavailable-signal scope list like every other report string.
_KEY_SCOPE_LIMIT = 20


def _frontmatter_keys(record: dict) -> set[str]:
    """Top-level frontmatter keys observed on one instance (bounded by input)."""
    keys: set[str] = set()
    for partition in ("portable_frontmatter", "frontmatter_extensions"):
        mapping = record.get(partition)
        if isinstance(mapping, dict):
            keys.update(str(key) for key in mapping)
    return keys


def _record_key_scopes(record: dict) -> tuple[set[str], set[str]]:
    """Consumers and unsupported scopes represented by one physical instance."""
    scopes = {str(record.get("scope") or "")}
    for alias in record.get("_aliases", []):
        if isinstance(alias, dict):
            scopes.add(str(alias.get("scope") or ""))
    consumers: set[str] = set()
    unsupported: set[str] = set()
    for scope in scopes:
        mapped = _KEY_SCOPE_CONSUMERS.get(scope)
        if mapped is None:
            if scope and scope != "all":
                unsupported.add(scope)
            continue
        consumers.update(mapped)
    return consumers, unsupported


def _key_finding(key: str, documenting: list[str], missing: list[str],
                 records: list[dict]) -> dict:
    """One bounded advisory finding for a behavioural key some consumer ignores."""
    documenting_labels = [key_support.label(consumer) for consumer in documenting]
    missing_labels = [key_support.label(consumer) for consumer in missing]
    sources = sorted(
        {url for consumer in missing if (url := key_support.source(consumer))}
    )
    title = f"`{key}` has no documented effect in " + ", ".join(missing_labels)
    explanation = (
        f"`{key}` has a documented behavioural effect in Claude Code, but the "
        "consumer(s) reading this instance do not document it. "
    )
    if documenting_labels:
        explanation += "Documented by: " + ", ".join(documenting_labels) + ". "
    explanation += (
        "This is not a rejection claim: only the claude.ai upload and Skills API "
        "surfaces are documented to reject unknown keys."
    )
    evidence = {
        "key": key,
        "documented_by": documenting_labels,
        "not_documented_by": missing_labels,
        "sources": sources,
    }
    if key == "disable-model-invocation" and "codex" in missing:
        evidence["codex_implicit_invocation"] = (
            "agents/openai.yaml -> policy.allow_implicit_invocation"
        )
        explanation += (
            " Codex sets implicit invocation in agents/openai.yaml "
            "(policy.allow_implicit_invocation)."
        )
    if sources:
        explanation += " Source: " + ", ".join(sources) + "."
    return _finding(
        "ignored-frontmatter", "info", "documented", title, explanation, records,
        evidence,
        "Review whether this key is needed; it only has effect where documented.",
    )


def _bounded_scope_names(unsupported: set[str]) -> list[str]:
    """Sorted, length-bounded scope names for the unavailable signal."""
    return sorted(_bounded(name, 128) for name in unsupported)


def _key_unavailable_signal(unsupported: set[str]) -> dict:
    """One bounded signal naming scopes with no documented key list."""
    names = _bounded_scope_names(unsupported)
    signal = {
        "signal": "frontmatter-key-support",
        "explanation": "no documented frontmatter key list is recorded for scope(s): "
        + ", ".join(names[:_KEY_SCOPE_LIMIT]),
    }
    if len(names) > _KEY_SCOPE_LIMIT:
        signal["scopes_total"] = len(names)
        signal["scopes_truncated"] = True
    return signal


def _extend_key_support(findings: list[dict], unavailable: list[dict],
                        records: list[dict]) -> None:
    """Append ignored-frontmatter findings and the unavailable scope signal."""
    key_findings, key_unsupported = _key_support_findings(records)
    findings.extend(key_findings)
    if key_unsupported:
        unavailable.append(_key_unavailable_signal(key_unsupported))


def _key_support_findings(records: list[dict]) -> tuple[list[dict], set[str]]:
    """Report behavioural keys the reading consumer(s) do not document.

    A key is only reported when it appears in an instance's top-level
    frontmatter, has a documented behavioural effect in Claude Code, and at
    least one consumer reading that scope does not document it.  Unknown keys
    with no documented effect anywhere are not reported: there is no effect to
    lose.
    """
    grouped: dict[str, dict] = {}
    unsupported: set[str] = set()
    behavioural = set(key_support.BEHAVIOURAL_KEYS)
    for record in records:
        consumers, record_unsupported = _record_key_scopes(record)
        unsupported.update(record_unsupported)
        if not consumers:
            continue
        for key in sorted(_frontmatter_keys(record) & behavioural):
            entry = grouped.setdefault(key, {"records": [], "consumers": set()})
            entry["records"].append(record)
            entry["consumers"].update(consumers)
    findings = []
    for key in sorted(grouped):
        entry = grouped[key]
        documenting = sorted(
            consumer for consumer in entry["consumers"]
            if key_support.documents(consumer, key)
        )
        missing = sorted(
            consumer for consumer in entry["consumers"]
            if not key_support.documents(consumer, key)
        )
        if not missing:
            continue
        findings.append(_key_finding(key, documenting, missing, entry["records"]))
    return findings, unsupported


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


def _home_prefix(home) -> str:
    """The resolved home directory, for displaying paths as ``~/…``."""
    base = home
    if base is None:
        try:
            base = paths.home_dir()
        except (OSError, RuntimeError):
            return ""
    try:
        return str(Path(str(base)).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return ""


def _redacted_path(value, home_prefix: str) -> str:
    """A bounded path with the home directory shown as ``~``."""
    if not value:
        return "path unavailable"
    text = _bounded(value, MAX_STRING)
    if home_prefix and (text == home_prefix or text.startswith(home_prefix + os.sep)):
        return "~" + text[len(home_prefix):]
    return text


def _listing_path(record: dict, home_prefix: str) -> str:
    """A bounded, home-redacted path for the listing evidence."""
    return _redacted_path(record.get("physical_path") or record.get("path") or "", home_prefix)


def _listing_description(record: dict) -> str:
    """``description`` plus ``when_to_use``, the two fields the cap applies to."""
    description = record.get("description")
    description = description if isinstance(description, str) else ""
    extensions = record.get("frontmatter_extensions")
    when = extensions.get("when_to_use") if isinstance(extensions, dict) else None
    return description + (when if isinstance(when, str) else "")


def _record_scopes(record: dict) -> set[str]:
    scopes = {str(record.get("scope") or "")}
    for alias in record.get("_aliases", []):
        if isinstance(alias, dict):
            scopes.add(str(alias.get("scope") or ""))
    return scopes


def _scan_project_claude_listing(project_root, degraded: list[dict]) -> list[dict]:
    """Observe project ``.claude/skills`` for a report that carries a project root."""
    try:
        root = Path(project_root).expanduser() / ".claude" / "skills"
        if not root.is_dir():
            return []
        rows = loader.scan_dir(root)
    except (OSError, RuntimeError, ValueError) as exc:
        degraded.append({"section": "claude-listing", "reason": _bounded(str(exc))})
        return []
    for row in rows:
        row["scope"] = _CLAUDE_PROJECT_SCOPE
        row["scope_label"] = "Project .claude"
        row["consumer"] = "claude-code"
        row["path"] = row.get("path") or str(root / str(row.get("name", "")))
        row["physical_path"] = _memoized_identity(row["path"])
    return rows


def _claude_listing_records(prepared: list[dict], project_root,
                            degraded: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split observed instances into Claude Code's personal and project roots."""
    personal, project, seen = [], [], set()
    for record in prepared:
        scopes = _record_scopes(record)
        if _CLAUDE_PERSONAL_SCOPE in scopes:
            personal.append(record)
        elif _CLAUDE_PROJECT_SCOPE in scopes:
            project.append(record)
        seen.add(_identity(record))
    if project_root is not None:
        for row in _scan_project_claude_listing(project_root, degraded):
            if _identity(row) not in seen:
                project.append(row)
                seen.add(_identity(row))
    return personal, project


def _frontmatter_value(record: dict, key: str):
    for partition in ("portable_frontmatter", "frontmatter_extensions"):
        mapping = record.get(partition)
        if isinstance(mapping, dict) and key in mapping:
            return mapping[key]
    return None


def _listing_hidden_reason(record: dict, state) -> str | None:
    """Which documented rule keeps a skill out of Claude's listing, if any.

    Per code.claude.com/docs/en/skills: skillOverrides "off" and
    "user-invocable-only" are "Hidden" from the listing, and frontmatter
    ``disable-model-invocation: true`` keeps the description out of context.
    """
    if record.get("disabled"):
        return "disabled"
    if record.get("document_missing") or record.get("decode_error"):
        return "unreadable"
    if state == "off":
        return "skillOverrides_off"
    if state == "user-invocable-only":
        return "skillOverrides_user_invocable_only"
    if _frontmatter_value(record, "disable-model-invocation") is True:
        return "disable_model_invocation"
    return None


def _listing_entry(record: dict, cap: int, setting: dict | None,
                   excluded: dict, home_prefix: str) -> tuple[dict, str] | None:
    """One listed entry and its listing text, or ``None`` when not listed."""
    hidden = _listing_hidden_reason(record, (setting or {}).get("observed_setting"))
    if hidden:
        excluded[hidden] += 1
        return None
    state = (setting or {}).get("observed_setting")
    name = _bounded(record.get("name", ""), 128)
    combined = _listing_description(record)
    listing = "name-only" if state == "name-only" else "full"
    if listing == "name-only":
        excluded["name_only"] += 1
    text = name if listing == "name-only" or not combined else f"{name}: {combined[:cap]}"
    entry = {
        "name": name,
        "scope": _bounded(record.get("scope", ""), 128),
        "path": _listing_path(record, home_prefix),
        "listing": listing,
        "description_chars": len(combined),
        "counted_description_chars": min(len(combined), cap) if listing == "full" else 0,
        "over_cap": listing == "full" and len(combined) > cap,
        "entry_chars": len(text),
    }
    return entry, text


def _collect_listing(records: list[dict], cap: int, settings: dict,
                     home_prefix: str) -> tuple[list[tuple[dict, str, dict]], list[str], dict]:
    """Build the listing entries in stable input order."""
    pairs: list[tuple[dict, str, dict]] = []
    over_cap: list[str] = []
    excluded = {"disabled": 0, "skillOverrides_off": 0, "unreadable": 0, "name_only": 0,
                "skillOverrides_user_invocable_only": 0, "disable_model_invocation": 0}
    for record in records:
        built = _listing_entry(
            record, cap, settings.get(str(record.get("name", ""))), excluded, home_prefix
        )
        if built is None:
            continue
        entry, text = built
        pairs.append((entry, text, record))
        if entry["over_cap"]:
            over_cap.append(entry["name"])
    return pairs, over_cap, excluded


def _name_only_candidates(pairs: list[tuple[dict, str, dict]],
                          limit: int) -> tuple[dict, list[dict]]:
    """Largest descriptions that switching to name-only would remove from the listing."""
    ranked = sorted(
        ((entry, record) for entry, _text, record in pairs if entry["listing"] == "full"),
        key=lambda item: (
            -item[0]["description_chars"],
            str(item[0]["name"]).casefold(),
            str(item[0]["path"]),
        ),
    )
    shown = ranked[:limit]
    section = {
        "candidates": [
            {
                "name": entry["name"],
                "path": entry["path"],
                "description_chars": entry["description_chars"],
                "freed_chars": max(0, entry["entry_chars"] - len(entry["name"])),
            }
            for entry, _record in shown
        ],
        "total": len(ranked),
        "omitted": max(0, len(ranked) - len(shown)),
        "wording": LISTING_CANDIDATE_WORDING,
    }
    return section, [record for _entry, record in shown]


def _listing_budget(observation: dict, window: str) -> dict:
    """Resolve the documented character budget, stating which basis was used."""
    env = observation.get("env_budget") or {}
    window_tokens = WINDOWS[window]
    if env.get("status") == "set":
        chars = int(env["value"])
        return {
            "basis": f"env {native_state.LISTING_BUDGET_ENV}",
            "budget_chars": chars,
            "budget_tokens": None,
            "budget_chars_estimate": chars,
            "window": window,
            "window_tokens": window_tokens,
            "fraction": None,
            "env_status": env.get("status"),
            "assumption": (
                "the environment variable states the budget directly in characters; "
                "no token conversion is applied"
            ),
        }
    fraction = observation.get("budget_fraction")
    basis = "skillListingBudgetFraction setting"
    if fraction is None:
        fraction = native_state.DEFAULT_LISTING_BUDGET_FRACTION
        basis = "default 1% of the context window (no skillListingBudgetFraction setting observed)"
    tokens = fraction * window_tokens
    return {
        "basis": basis,
        "budget_chars": None,
        "budget_tokens": int(round(tokens)),
        "budget_chars_estimate": int(round(tokens * LISTING_CHARS_PER_TOKEN)),
        "window": window,
        "window_tokens": window_tokens,
        "fraction": fraction,
        "env_status": env.get("status"),
        "assumption": LISTING_ESTIMATE_ASSUMPTION,
    }


def _listing_status(listing_chars: int, budget_chars: int, partial: bool) -> str:
    """The budget verdict; partial settings evidence could hide overrides."""
    if partial:
        return "unknown"
    return "over_budget_estimate" if listing_chars > budget_chars else "within_budget"


def _listing_partial_reasons(unreadable: bool, project_root) -> list[str]:
    """Why the listing estimate is partial, in words.

    Project settings can set ``skillOverrides`` for personal skills too, so a
    report without a project root cannot have seen every override. That keeps
    the estimate but marks it partial; only an unreadable settings file makes
    the verdict itself ``unknown``.
    """
    reasons = []
    if unreadable:
        reasons.append("a Claude Code settings file could not be parsed, so an "
                       "override may be hidden; the budget verdict is unknown")
    if project_root is None:
        reasons.append("project settings were not read (no project root), so a "
                       "project skillOverrides entry could change this estimate")
    return reasons


def _native_partial(observation: object) -> bool:
    """True when a settings source exists but could not be parsed.

    ``missing`` (no file) and ``unobserved`` (no project context) cannot hide a
    declaration; only an unreadable or invalid file can, and that is the case
    the listing estimate must disclose.
    """
    if not isinstance(observation, dict):
        return True
    return any(
        isinstance(entry, dict) and entry.get("status") in ("unavailable", "invalid")
        for entry in observation.get("sources", [])
    )


def _note_listing_scope(unavailable: list[dict], section: dict) -> None:
    """Record that this report observed no Claude Code instances at all."""
    if section.get("instances_observed"):
        return
    unavailable.append({
        "signal": "claude-listing-scope",
        "explanation": (
            "no Claude Code scope instances were observed in this report, so the "
            "skill-listing budget was not estimated"
        ),
    })


def _project_listing_state(project_root, project_records: list[dict],
                           home_prefix: str) -> dict:
    """Project-root context, or an explicit unavailable signal."""
    if project_root is None:
        return {
            "state": "unavailable",
            "reason": (
                "this report carries no project root, so project .claude/skills "
                "instances were not observed"
            ),
        }
    return {
        "state": "observed",
        "root": _redacted_path(project_root, home_prefix),
        "instances": len(project_records),
    }


def _claude_listing_finding(section: dict, records: list[dict]) -> dict:
    """One advisory finding when the estimate exceeds the budget."""
    budget = section["budget"]
    return _finding(
        "claude-listing-budget", "info", "heuristic",
        "Claude Code's skill listing may exceed its character budget",
        (
            f"The observed listing is {section['listing_chars']} characters against an "
            f"estimated budget of {budget['budget_chars_estimate']} "
            f"({budget['basis']}); the conversion is an estimate, not a measurement."
        ),
        records,
        {
            "status": section["status"],
            "listing_chars": section["listing_chars"],
            "budget": budget,
            "chars_to_free": section["chars_to_free"],
            "name_only_candidates": section["name_only_candidates"]["total"],
            "candidates_by_size_only": True,
        },
        "Review the name-only candidates in the claude_listing section; this tool cannot know which descriptions are actually dropped.",
    )


def _claude_listing_section(prepared: list[dict], *, home, project_root, window: str,
                            degraded: list[dict]) -> tuple[dict, list[dict]]:
    """Estimate Claude Code's skill-listing budget from observed instances."""
    home_prefix = _home_prefix(home)
    observation = native_state.observe_claude_listing(
        home=home_prefix or None, project=project_root
    )
    personal, project = _claude_listing_records(prepared, project_root, degraded)
    cap = observation.get("max_desc_chars") or native_state.DEFAULT_LISTING_MAX_DESC_CHARS
    names = sorted({str(r.get("name", "")) for r in personal + project if r.get("name")})
    settings = native_state.observe_native_states(
        "claude-code", names, home=home_prefix or None, project=project_root
    )
    partial = bool(observation.get("partial")) or any(
        _native_partial(item) for item in settings.values()
    )
    pairs, over_cap, excluded = _collect_listing(
        personal + project, cap, settings, home_prefix
    )
    listing_text = _LISTING_SEPARATOR.join(text for _entry, text, _record in pairs)
    listing_chars = len(listing_text)
    listing_tokens, method = count_tokens(listing_text)
    budget = _listing_budget(observation, window)
    budget_chars = int(budget["budget_chars_estimate"])
    candidates, candidate_records = _name_only_candidates(pairs, MAX_LISTING_CANDIDATES)
    section = {
        "version": 1,
        "consumer": "claude-code",
        "source": _CLAUDE_LISTING_SOURCE,
        "effective_state": "unknown",
        "confidence": "partial" if (partial or project_root is None) else "observed",
        "partial_reasons": _listing_partial_reasons(partial, project_root),
        "status": _listing_status(listing_chars, budget_chars, partial),
        "instances_observed": len(personal) + len(project),
        "listed_skills": len(pairs),
        "entries": [entry for entry, _text, _record in pairs[:MAX_GROUP_INSTANCES]],
        "entries_total": len(pairs),
        "entries_truncated": len(pairs) > MAX_GROUP_INSTANCES,
        "listing_chars": listing_chars,
        "listing_tokens_estimate": listing_tokens,
        "listing_tokens_method": method,
        "listing_text_basis": LISTING_TEXT_BASIS,
        "max_description_chars": cap,
        "budget": budget,
        "chars_to_free": max(0, listing_chars - budget_chars),
        "name_only_candidates": candidates,
        "over_cap": {
            "count": len(over_cap),
            "names": over_cap[:MAX_LISTING_OVER_CAP],
            "omitted": max(0, len(over_cap) - MAX_LISTING_OVER_CAP),
            "max_description_chars": cap,
        },
        "excluded": excluded,
        "settings": observation,
        "project_skills": _project_listing_state(project_root, project, home_prefix),
    }
    findings = []
    if section["status"] == "over_budget_estimate":
        findings.append(_claude_listing_finding(section, candidate_records))
    return section, findings


_BRIDGE_SOURCE_SCOPE = "agents"
_BRIDGE_COPY_COMMAND = "skills-mgr sync <name> --from agents --to claude-code"
_BRIDGE_EXPLANATION = (
    "Claude Code documents ~/.claude/skills, project .claude/skills, managed and "
    "plugin skills, but not ~/.agents/skills, so a skill that exists only there "
    "is not loaded by Claude Code (anthropics/claude-code #31005 asks for it and "
    "is open)."
)
_BRIDGE_REMEDIES = (
    {
        "kind": "copy",
        "command": _BRIDGE_COPY_COMMAND,
        "note": "An independent copy; the hygiene report flags it if the copies later differ.",
    },
    {
        "kind": "link",
        "command": "ln -s ~/.agents/skills/<name> ~/.claude/skills/<name>",
        "note": (
            "Claude Code's handling of symlinked skill folders is reported unreliable "
            "(anthropics/claude-code #14836, open). This tool shows such a link "
            "read-only and keeps edits in ~/.agents/skills."
        ),
    },
)


def _bridge_candidate(record: dict) -> bool:
    """An enabled, readable copy in ``~/.agents/skills`` only."""
    scopes_seen = _record_scopes(record)
    return (
        _BRIDGE_SOURCE_SCOPE in scopes_seen
        and _CLAUDE_PERSONAL_SCOPE not in scopes_seen
        and not record.get("disabled")
        and not record.get("malformed")
    )


def _bridge_missing(prepared: list[dict]) -> list[dict]:
    claude_names = {
        str(r.get("name", "")) for r in prepared if _CLAUDE_PERSONAL_SCOPE in _record_scopes(r)
    }
    missing = [
        r for r in prepared
        if _bridge_candidate(r) and str(r.get("name", "")) not in claude_names
    ]
    return sorted(missing, key=_record_sort_key)


def _bridge_unavailable_reason(scope: str, degraded: list[dict]) -> tuple[str, str] | None:
    """Why the comparison cannot be made, as ``(state, reason)``, or ``None``."""
    if scope != "all":
        return "unavailable", "Comparing ~/.agents/skills with ~/.claude/skills needs --scope all."
    if any(item.get("truncated") for item in degraded):
        # A copy past the instance limit could be the one that closes a gap,
        # so a truncated scan must not name anything as missing.
        return "partial", "The physical-instance limit was reached, so the comparison is incomplete."
    return None


def _agents_bridge_section(prepared: list[dict], *, scope: str, home,
                           degraded: list[dict]) -> tuple[dict, list[dict]]:
    """Explain, read-only, which ~/.agents/skills skills Claude Code cannot see."""
    section = {
        "version": 1,
        "consumer": "claude-code",
        "source_scope": _BRIDGE_SOURCE_SCOPE,
        "source": _CLAUDE_LISTING_SOURCE,
        "explanation": _BRIDGE_EXPLANATION,
        "remedies": [dict(item) for item in _BRIDGE_REMEDIES],
        "writes_nothing": True,
        "missing": [],
        "missing_total": 0,
        "omitted": 0,
    }
    blocked = _bridge_unavailable_reason(scope, degraded)
    if blocked is not None:
        section["state"], section["reason"] = blocked
        return section, []
    home_prefix = _home_prefix(home)
    missing = _bridge_missing(prepared)
    section["state"] = "observed"
    section["missing"] = [
        {"name": _bounded(r.get("name", ""), 128), "path": _listing_path(r, home_prefix)}
        for r in missing[:MAX_BRIDGE_NAMES]
    ]
    section["missing_total"] = len(missing)
    section["omitted"] = max(0, len(missing) - MAX_BRIDGE_NAMES)
    if not missing:
        return section, []
    finding = _finding(
        "agents-bridge-gap", "info", "observed",
        f"{len(missing)} skill(s) in ~/.agents/skills are not visible to Claude Code",
        _BRIDGE_EXPLANATION,
        missing[:MAX_GROUP_INSTANCES],
        {"missing_total": len(missing), "copy_command": _BRIDGE_COPY_COMMAND},
        "Copy the ones Claude Code should use with the sync command; nothing was changed.",
    )
    return section, [finding]


_CODEX_CONFIG_SCOPES = frozenset({"codex", "all"})
_CODEX_CONFIG_EXPLANATION = (
    "Codex compares a [[skills.config]] path entry with the skill's SKILL.md file. "
    "An entry naming the skill folder, a missing file or another file matches no "
    "skill, so the setting it declares never applies (openai/codex#51044)."
)


def _codex_config_section(scope: str, home) -> tuple[dict, list[dict]]:
    """Explain, read-only, Codex config entries that can never match a skill."""
    if scope not in _CODEX_CONFIG_SCOPES:
        return {"version": 1, "state": "unavailable", "reason": "needs the codex or all scope",
                "entries": [], "total": 0, "omitted": 0, "writes_nothing": True}, []
    report = native_state.codex_config_dead_entries(home=home)
    prefix = _home_prefix(home)
    entries = [dict(entry, path=_redacted_path(entry["path"], prefix),
                    suggested_path=_redacted_path(entry["suggested_path"], prefix)
                    if entry["suggested_path"] else None) for entry in report["entries"]]
    section = {"version": 1, "state": report["state"],
               "config_path": _redacted_path(report["config_path"], prefix),
               "explanation": _CODEX_CONFIG_EXPLANATION, "entries": entries,
               "total": report["total"], "omitted": report["omitted"], "writes_nothing": True}
    if not report["total"]:
        return section, []
    finding = _finding(
        "codex-config-dead-entry", "warning", "observed",
        f"{report['total']} Codex skills.config path entr{'y matches' if report['total'] == 1 else 'ies match'} no skill",
        _CODEX_CONFIG_EXPLANATION, [], {"entries": entries[:MAX_GROUP_INSTANCES], "total": report["total"]},
        "Point each path entry at the skill's SKILL.md file (suggested_path when shown) or use name = ...; nothing was changed.",
    )
    return section, [finding]


def _source_lock_status(record: dict, path: str, degraded: list[dict]) -> dict:
    """Read one instance's source-lock state, degrading instead of raising."""
    try:
        return source_lock.source_lock_status(path)
    except Exception as exc:
        degraded.append({"instance": _bounded(_identity(record)), "section": "source-lock", "reason": _bounded(str(exc))})
        return {"state": "inaccessible", "error": str(exc)}


def _source_lock_finding(record: dict, status: dict) -> dict:
    """Turn one present source-lock state into a hygiene finding."""
    state = status.get("state", "inaccessible")
    lock = status.get("lock") if isinstance(status.get("lock"), dict) else {}
    if state == "changed":
        return _finding(
            "source-lock-drift", "warning", "observed",
            f"{record.get('name', '')} differs from its source lock",
            "The installed tree differs from the recorded source-lock content hash.",
            [record], {"state": state, "content_hash": status.get("content_hash")},
            "Inspect the exact source/update review before applying any deliberate change.",
        )
    if state == "inaccessible":
        return _finding(
            "source-lock-inaccessible", "warning", "observed",
            f"{record.get('name', '')} source evidence is inaccessible",
            "The source-lock sidecar or current tree could not be safely read or manifested.",
            [record], {"state": state, "error": _bounded(status.get("error", "source evidence unavailable"))},
            "Inspect the exact physical directory and source-lock sidecar permissions manually.",
        )
    if state == "unbound":
        return _finding(
            "source-lock-unbound", "warning", "observed",
            f"{record.get('name', '')} source-lock sidecar is not bound to this install",
            "No binding recorded in the manager's private data directory matches this sidecar, so it may have been forged or copied from another install.",
            [record], {
                "state": state,
                "recorded_state": status.get("recorded_state"),
                "install_binding": status.get("install_binding"),
                "content_hash": status.get("content_hash"),
            },
            "Treat this source evidence as unverified until a reviewed source/update is applied here.",
        )
    return _finding(
        "source-lock-evidence", "info", "observed",
        f"{record.get('name', '')} has source-lock evidence",
        "A source identity and recorded content hash are present; this is evidence, not a safety or trust verdict.",
        [record], {
            "state": state,
            "content_hash": status.get("content_hash"),
            "recorded_content_hash": lock.get("content_hash"),
            "checked_at": lock.get("checked_at"),
            "source": _safe_source(lock),
        },
        "Use the existing source/update review surface when inspecting this exact instance.",
    )


def _source_lock_findings(records: list[dict], unavailable: list[dict], degraded: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        path = _path(record)
        if path is None or record.get("addressable") is False:
            continue
        status = _source_lock_status(record, path, degraded)
        if status.get("state") == "missing":
            unavailable.append({
                "signal": "source-lock",
                "scope": record.get("scope", ""),
                "name": record.get("name", ""),
                "state": "missing",
                "explanation": "No source-lock sidecar is recorded for this physical instance; freshness and provenance are not observed.",
            })
            continue
        findings.append(_source_lock_finding(record, status))
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


def _lockfile_section(
    degraded: list[dict],
    *,
    project_root,
    home,
    xdg_state_home,
) -> dict:
    """Gather lockfile evidence without letting one unreadable lock abort the report."""
    try:
        # paths.home_dir() treats an empty HOME as unresolvable (SCOPE-17);
        # Path.home() would read /.agents instead.
        resolved_home = home if home is not None else paths.home_dir()
    except (OSError, RuntimeError, ValueError):
        resolved_home = None
    if xdg_state_home is None:
        xdg_state_home = os.environ.get("XDG_STATE_HOME") or None
    try:
        evidence = lockfiles.lockfile_evidence(
            resolved_home,
            project_root=project_root,
            xdg_state_home=xdg_state_home,
        )
        return _redact_lockfile_paths(evidence, _home_prefix(resolved_home))
    except Exception as exc:  # bounded evidence, never a report failure
        reason = _bounded(str(exc))
        degraded.append({"section": "lockfiles", "reason": reason})
        return lockfiles.unavailable_evidence(f"lockfile evidence was unavailable: {reason}")


def _redact_lockfile_paths(evidence: dict, home_prefix: str) -> dict:
    """Show home-relative lockfile paths as ``~``, like the rest of the report."""
    for kind in ("global", "project"):
        lock = evidence.get(kind)
        if not isinstance(lock, dict):
            continue
        for key in ("path", "installed_root"):
            if lock.get(key):
                lock[key] = _redacted_path(lock[key], home_prefix)
        for row in lock.get("entries") or []:
            if isinstance(row, dict) and row.get("installed_path"):
                row["installed_path"] = _redacted_path(row["installed_path"], home_prefix)
    for signal in evidence.get("unavailable_signals") or []:
        if isinstance(signal, dict) and signal.get("path"):
            signal["path"] = _redacted_path(signal["path"], home_prefix)
    return evidence


def _report_extras(project_root, home, xdg_state_home) -> dict:
    """Pass optional context through to the report only when supplied."""
    extras = {}
    for key, value in (
        ("project_root", project_root),
        ("home", home),
        ("xdg_state_home", xdg_state_home),
    ):
        if value is not None:
            extras[key] = value
    return extras


def hygiene_report(
    records: list[dict],
    *,
    scope: str,
    max_instances: int = 10_000,
    project_root=None,
    home=None,
    xdg_state_home=None,
    window: str = DEFAULT_WINDOW,
) -> dict:
    """Build a stable JSON-safe read-only hygiene report."""
    token = _RESOLVED_IDENTITIES.set({})
    try:
        return _hygiene_report(
            records,
            scope=scope,
            max_instances=max_instances,
            window=window_name(window),
            **_report_extras(project_root, home, xdg_state_home),
        )
    finally:
        _RESOLVED_IDENTITIES.reset(token)


def _hygiene_report(
    records: list[dict],
    *,
    scope: str,
    max_instances: int,
    window: str,
    project_root=None,
    home=None,
    xdg_state_home=None,
) -> dict:
    prepared, degraded = _prepare_records(records, max_instances)
    unavailable = _unavailable_signals()
    findings = _validation_findings(prepared)
    findings.extend(_parse_risk_findings(prepared))
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
    _extend_key_support(findings, unavailable, prepared)
    context_findings, largest = _context_findings(prepared)
    findings.extend(context_findings)
    findings.extend(_source_lock_findings(prepared, unavailable, degraded))
    lockfile_section = _lockfile_section(
        degraded,
        project_root=project_root,
        home=home,
        xdg_state_home=xdg_state_home,
    )
    claude_listing, listing_findings = _claude_listing_section(
        prepared,
        home=home,
        project_root=project_root,
        window=window,
        degraded=degraded,
    )
    findings.extend(listing_findings)
    _note_listing_scope(unavailable, claude_listing)
    agents_bridge, bridge_findings = _agents_bridge_section(
        prepared, scope=scope, home=home, degraded=degraded
    )
    findings.extend(bridge_findings)
    codex_config, codex_findings = _codex_config_section(scope, home)
    findings.extend(codex_findings)
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
        "lockfiles": lockfile_section,
        "claude_listing": claude_listing,
        "agents_bridge": agents_bridge,
        "codex_config": codex_config,
        "unavailable_signals": sorted(unavailable, key=lambda item: (str(item.get("signal", "")), str(item.get("name", "")))),
        "degraded": sorted(degraded, key=lambda item: (str(item.get("section", "")), str(item.get("instance", "")), str(item.get("reason", "")))),
        "limits": {
            "max_instances": max_instances,
            "max_candidate_pairs": MAX_PAIRS,
            "max_near_duplicate_findings": MAX_NEAR_RESULTS,
            "max_findings": MAX_FINDINGS,
            "max_group_instances": MAX_GROUP_INSTANCES,
            "max_feature_posting": MAX_FEATURE_POSTING,
            "max_description_characters": validator.MAX_DESCRIPTION,
            "max_heading_characters": MAX_HEADING_CHARS,
            "max_shared_features": MAX_SHARED_FEATURES,
            "max_string": MAX_STRING,
            "max_listing_candidates": MAX_LISTING_CANDIDATES,
            "max_listing_over_cap": MAX_LISTING_OVER_CAP,
            "max_bridge_names": MAX_BRIDGE_NAMES,
        },
    }
    return result


__all__ = [
    "HygieneError",
    "normalize_instruction_body",
    "near_duplicate_candidates",
    "hygiene_report",
]

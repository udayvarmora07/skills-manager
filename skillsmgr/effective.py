"""Read-only effective-resolution diagnostic for one consumer and project.

Issue #12 / TODO L3: derive, at read time, which instance of a skill a consumer
would load for one ``(consumer, project-CWD, skill)`` triple — and say so
honestly when the documented rules do not determine a winner.

Scope rules honoured here:

* Nothing is persisted, cached, or written. Every value is derived from the
  filesystem through existing read seams (``loader.scan_dir`` observations plus
  the facade roots in ``scopes.known_scopes``); there is no new ``Store``
  method, no SQLite access, and no schema or ``SCHEMA_VERSION`` change.
* ``effective_state`` stays ``unresolved`` everywhere else (ADR-002). This
  module is a diagnostic, not the approval-gated runtime
  ``ConsumerRootBinding`` model.
* Every precedence row cites the primary source recorded in
  ``docs/12-agent-root-discovery-2026-09-08.md``. A consumer whose same-name
  order is not recorded there (Cursor, Opencode) returns an explicit
  ``undocumented-precedence`` result, and an unknown consumer returns
  ``unknown-consumer`` — never a guess.

Instance states reuse the observed vocabulary: a ``disabled`` document is
``SKILL.md.disabled`` and a consumer scanning for ``SKILL.md`` cannot see it, so
it is reported as skipped rather than loadable; an ``invalid`` (malformed or
undecodable) document is reported but cannot be the effective guidance.
"""

from __future__ import annotations

import os
from pathlib import Path

from .loader import scan_dir

#: Bounds: a diagnostic must never walk an unbounded tree. ``MAX_ROOTS`` caps
#: the nested-root search results, ``MAX_INSTANCES`` the instances read overall,
#: and ``MAX_WALK_ENTRIES``/``MAX_WALK_DEPTH`` the *work*.
#:
#: SEC-2: ``MAX_ROOTS`` alone bounded results, not effort. ``Path.rglob`` is a
#: generator that has to descend the entire tree to prove no further match
#: exists, so a ``project`` with no nested skills root made one unauthenticated
#: GET walk a caller-chosen directory to completion (``project=/`` never
#: returned). The walk below is bounded by entries visited and depth reached.
MAX_ROOTS = 32
MAX_INSTANCES = 500
MAX_WALK_ENTRIES = 2000
MAX_WALK_DEPTH = 8

#: SEC-3: an unauthenticated HTTP caller must never be handed the user's real
#: home directory or agent-skill inventory. Paths outside the allowlisted root
#: are replaced by these markers in the report; the local CLI passes
#: ``disclose_paths=True`` (it runs as the user who can already read them).
REDACTED_PROJECT = "<redacted: outside the managed skill directories>"
REDACTED_ROOT = "<redacted>"
REDACTION_NOTE = (
    "paths outside this manager's data directory are redacted; pass "
    "--project with a path inside the data directory, or run the CLI with "
    "--disclose-paths for the full local view"
)
#: A report is small; an oversized one is a symptom, not a payload.
MAX_REPORT_INSTANCES = MAX_INSTANCES

#: Reported on every result; the runtime contract itself is unchanged.
UNRESOLVED = "unresolved"

#: ``ordered`` elects the highest documented tier; ``no-merge`` and
#: ``undocumented`` deliberately elect nobody.
POLICY_OUTCOMES = {
    "ordered": "resolved",
    "no-merge": "no-merge",
    "undocumented": "undocumented-precedence",
}

# Root specs: ``scope`` reuses a facade root from ``scopes.known_scopes`` (one
# place owns the path), ``rel`` is a documented project-relative path, ``path``
# is a documented absolute path, ``nested`` marks the both-load nested scan, and
# ``path_known`` False marks a documented tier whose path this tool cannot read.
CONSUMERS: dict[str, dict] = {
    "claude-code": {
        "label": "Claude Code",
        "source": "https://code.claude.com/docs/en/skills",
        "policy": "ordered",
        "tiers": (
            {
                "id": "enterprise",
                "label": "Enterprise (managed)",
                "roots": ({"path_known": False},),
                "note": "documented as the highest tier, but no enterprise path is "
                "recorded in docs/12-agent-root-discovery-2026-09-08.md, so this "
                "tier is unobservable here and any lower-tier win is provisional",
            },
            {
                "id": "personal",
                "label": "Personal (user)",
                "roots": ({"scope": "claude-code"},),
            },
            {
                "id": "project",
                "label": "Project",
                "roots": ({"rel": ".claude/skills"},),
            },
        ),
        "both_load": {
            "rel": ".claude/skills",
            "reason": "project-root and nested skills both load (directory-qualified "
            "form), so nested copies are not shadowed by the project winner",
        },
        "notes": (
            "skills beat .claude/commands/ files; user skills replace bundled skills "
            "but not their aliases; claude.ai-synced skills always lose to any other "
            "command (not detectable from the filesystem here)",
        ),
    },
    "codex": {
        "label": "Codex",
        "source": "https://learn.chatgpt.com/docs/build-skills",
        "policy": "no-merge",
        "tiers": (
            {
                "id": "repo",
                "label": "REPO (.agents/skills, CWD to repo root)",
                "roots": ({"rel": ".agents/skills", "recursive": True},),
            },
            {"id": "user", "label": "USER ($HOME/.agents/skills)", "roots": ({"scope": "agents"},)},
            {"id": "admin", "label": "ADMIN (/etc/codex/skills)", "roots": ({"path": "/etc/codex/skills"},)},
            {
                "id": "system",
                "label": "SYSTEM (bundled with Codex)",
                "roots": ({"path_known": False},),
                "note": "bundled skills ship inside Codex and are not on the paths read here",
            },
        ),
        "notes": (
            "same-name skills do NOT merge: both copies can appear in selectors, so "
            "no winner is elected",
        ),
        "facade_scope": "codex",
        "facade_warning": (
            "the facade scope id 'codex' (~/.codex/skills) is compatibility-only and "
            "is NOT a documented Codex skills root; anything found there is reported "
            "as a facade-only observation, never as a REPO/USER/ADMIN win"
        ),
    },
    "cursor": {
        "label": "Cursor",
        "source": "https://prod.cursor.com/docs/skills",
        "policy": "undocumented",
        "tiers": (
            {"id": "user", "label": "User (~/.cursor/skills)", "roots": ({"scope": "cursor"},)},
            {"id": "user-agents", "label": "User (~/.agents/skills)", "roots": ({"scope": "agents"},)},
            {"id": "project", "label": "Project (.cursor/skills)", "roots": ({"rel": ".cursor/skills"},)},
            {"id": "project-agents", "label": "Project (.agents/skills)", "roots": ({"rel": ".agents/skills"},)},
            {
                "id": "nested",
                "label": "Nested project roots",
                "roots": ({"rel": ".cursor/skills", "nested": True},),
                "note": "nested skills are scoped to files below their own directory",
            },
        ),
        "notes": (
            "Cursor documents nested/project scoping and startup discovery but no "
            "same-name order across roots, so no winner is derived",
        ),
    },
    "opencode": {
        "label": "Opencode",
        "source": "https://opencode.ai/docs/skills/",
        "policy": "undocumented",
        "tiers": (
            {"id": "user", "label": "User (~/.config/opencode/skills)", "roots": ({"scope": "opencode"},)},
            {"id": "user-claude", "label": "User compat (~/.claude/skills)", "roots": ({"scope": "claude-code"},)},
            {"id": "user-agents", "label": "User (~/.agents/skills)", "roots": ({"scope": "agents"},)},
            {"id": "project", "label": "Project (.opencode/skills)", "roots": ({"rel": ".opencode/skills"},)},
            {"id": "project-claude", "label": "Project compat (.claude/skills)", "roots": ({"rel": ".claude/skills"},)},
            {"id": "project-agents", "label": "Project compat (.agents/skills)", "roots": ({"rel": ".agents/skills"},)},
        ),
        "notes": (
            "Opencode documents that the later source wins and that project roots are "
            "searched from the repository root toward the current directory, but this "
            "facade carries no repository-root input and exposes three compatibility "
            "roots per level, so the cross-root order is not derived",
        ),
    },
    "gemini": {
        "label": "Gemini CLI",
        "source": "https://geminicli.com/docs/cli/using-agent-skills/",
        "policy": "ordered",
        "tiers": (
            {
                "id": "workspace",
                "label": "Workspace",
                "roots": ({"rel": ".gemini/skills"}, {"rel": ".agents/skills"}),
                "note": "both workspace roots are documented with no recorded order "
                "between them, so a same-tier tie is reported as ambiguous",
            },
            {
                "id": "user",
                "label": "User",
                "roots": ({"scope": "gemini"}, {"scope": "agents"}),
                "note": "the ~/.agents/skills alias is documented alongside "
                "~/.gemini/skills with no recorded order between them",
            },
            {
                "id": "extension",
                "label": "Extension",
                "roots": ({"path_known": False},),
                "note": "extensions install skills outside the paths read here",
            },
            {
                "id": "built-in",
                "label": "Built-in",
                "roots": ({"path_known": False},),
                "note": "bundled skills are not on the paths read here",
            },
        ),
        "notes": "documented order, lowest to highest: built-in < extension < user < workspace",
    },
    "commandcode": {
        "label": "Command Code",
        "source": "https://commandcode.ai/docs/skills",
        "policy": "ordered",
        "tiers": (
            {"id": "project-commandcode", "label": "Project .commandcode/", "roots": ({"rel": ".commandcode/skills"},)},
            {
                "id": "project-agents",
                "label": "Project .agents/ (walked from CWD, stops at $HOME)",
                "roots": ({"rel": ".agents/skills", "recursive": True},),
            },
            {"id": "user-commandcode", "label": "User ~/.commandcode/", "roots": ({"scope": "commandcode"},)},
            {"id": "user-agents", "label": "User ~/.agents/", "roots": ({"scope": "agents"},)},
            {
                "id": "extras",
                "label": "Extra locations (--skill flags, settings.json skills)",
                "roots": ({"path_known": False},),
                "note": "extra locations come from CLI flags and settings.json, which "
                "this read-only diagnostic does not parse, so a lower observed tier "
                "win is provisional and an extra location could outrank it",
            },
            {
                "id": "bundled",
                "label": "Bundled",
                "roots": ({"path_known": False},),
                "note": "bundled skills are not on the paths read here",
            },
        ),
        "notes": (
            "full six-way order: project .commandcode/ > project .agents/ > user "
            "~/.commandcode/ > user ~/.agents/ > extras > bundled; same-name losers "
            "surface as 'Duplicate names' warnings and are never dropped silently "
            "(the /skill:<name> hatch can still force a lower instance)",
        ),
    },
}


def known_consumers() -> tuple[str, ...]:
    """Return the consumers with a recorded precedence row."""
    return tuple(sorted(CONSUMERS))


def _facade_root(scope_id: str) -> Path | None:
    """Return one facade root by scope id, or ``None`` when it is unknown."""
    from . import scopes

    for scope in scopes.known_scopes():
        if scope.id == scope_id:
            return scope.base
    return None


def _resolve_root(root_spec: dict, project: Path | None) -> Path | None:
    """Resolve one root spec to a physical path, or ``None`` when unreadable."""
    if root_spec.get("scope"):
        return _facade_root(str(root_spec["scope"]))
    if root_spec.get("path"):
        return Path(str(root_spec["path"]))
    if root_spec.get("rel") and project is not None:
        return project / str(root_spec["rel"])
    return None


def _physical(path: Path | str | None) -> Path | None:
    """Return the physical identity of *path* for alias deduplication.

    SCOPE-7: the diagnostic never used ``root_discovery.resolved_root``, so a
    root reached through a symlink (``.gemini/skills -> .agents/skills``) was
    scanned twice: one physical file became two candidates and the tier was
    reported ``ambiguous``, and in an ordered policy the winner was listed as
    its own ``shadowed`` copy.  ADR-002 invariant 1 says aliases do not create a
    second root, and this is the same rule for the diagnostic.
    """
    if path is None:
        return None
    try:
        return Path(os.path.realpath(str(path)))
    except (OSError, ValueError):
        return None


def _scan_root_once(root: Path, budget: dict) -> bool:
    """Claim *root*'s physical identity; False when it was already scanned."""
    physical = _physical(root)
    if physical is None:
        return True
    if physical in budget["physical_roots"]:
        return False
    budget["physical_roots"].add(physical)
    return True


def _contains(root: Path, candidate: Path) -> bool:
    """True when *candidate* is *root* or sits below it."""
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _allowed_roots(allowed_root) -> list[Path]:
    """Normalise the confinement boundary into a list of absolute roots."""
    if allowed_root is None:
        return []
    if isinstance(allowed_root, (str, Path)):
        candidates = [allowed_root]
    else:
        candidates = list(allowed_root)
    roots: list[Path] = []
    for candidate in candidates:
        if candidate is None:
            continue
        roots.append(Path(candidate).expanduser().resolve())
    return roots


def _under_any(roots: list[Path], candidate: Path) -> bool:
    """True when *candidate* sits inside any allowlisted root."""
    return any(_contains(root, candidate) for root in roots)


def _bounded_walk(root: Path, rel: str, budget: dict) -> list[Path]:
    """Find ``rel`` directories below *root*, bounded by work not by results.

    Depth-first over ``os.scandir`` (not ``rglob``), stopping as soon as
    ``MAX_WALK_ENTRIES`` entries have been visited or ``MAX_WALK_DEPTH`` levels
    have been reached.  A directory with no match therefore costs a bounded
    amount of work instead of a full-tree traversal (SEC-2).
    """
    wanted = Path(rel)
    if wanted.is_absolute() or ".." in wanted.parts:
        return []
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 1)]
    while stack:
        base, depth = stack.pop()
        if budget["entries"] >= MAX_WALK_ENTRIES:
            budget["walk_truncated"] = True
            break
        try:
            entries = list(os.scandir(base))
        except OSError:
            continue
        budget["entries"] += len(entries)
        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            child = Path(entry.path)
            if child.name == wanted.name and child != root / rel:
                found.append(child)
                if len(found) >= MAX_ROOTS:
                    return sorted(found)
            if depth < MAX_WALK_DEPTH:
                stack.append((child, depth + 1))
    return sorted(found)


def _nested_roots(project: Path | None, rel: str, budget: dict) -> list[Path]:
    """Project-relative roots below the project root (nested discovery).

    *budget* is the caller's shared diagnostic budget; ``entries`` is the walk
    work counter and ``walk_truncated`` records that the bound was hit.
    """
    if project is None or not project.is_dir() or not rel:
        return []
    return _bounded_walk(project, rel, budget)


def _read_root(root: Path | None, *, tier: str, recursive: bool = False,
               scope: str | None = None) -> list[dict]:
    """Read one root's instances through the shared loader seam."""
    if root is None or not root.is_dir():
        return []
    instances = []
    for record in scan_dir(root, recursive=recursive):
        instance = dict(record)
        instance.setdefault("path", str(root / str(record.get("name", ""))))
        instance["root"] = str(root)
        instance["tier"] = tier
        instance["scope"] = scope
        instances.append(instance)
    return instances


def _classify(instances: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split instances into loadable ones and skipped ones with a reason."""
    loadable: list[dict] = []
    skipped: list[dict] = []
    for instance in instances:
        reason = None
        if instance.get("disabled"):
            reason = "disabled (SKILL.md.disabled is not loadable as SKILL.md)"
        elif instance.get("malformed"):
            reason = "invalid document (frontmatter or encoding)"
        if reason is None:
            loadable.append(instance)
        else:
            skipped.append(dict(instance, skipped_reason=reason))
    return loadable, skipped


def _instance_state(instance: dict) -> str:
    """Observed state of one instance in the shared state vocabulary."""
    if instance.get("disabled"):
        return "disabled"
    if instance.get("malformed"):
        return "invalid"
    return "loadable"


def _public_instance(instance: dict) -> dict:
    """Return the diagnostic-facing projection of one instance."""
    return {
        "name": instance.get("name"),
        "path": instance.get("path"),
        "root": instance.get("root"),
        "tier": instance.get("tier"),
        "scope": instance.get("scope"),
        "state": _instance_state(instance),
        "skipped_reason": instance.get("skipped_reason"),
        "disabled": bool(instance.get("disabled")),
        "malformed": bool(instance.get("malformed")),
        "decode_error": instance.get("decode_error"),
        "description": instance.get("description") or "",
        "effective_state": UNRESOLVED,
    }


def _tier_report(tier: dict) -> dict:
    return {
        "id": tier["id"],
        "label": tier["label"],
        "roots": [str(root) for root in tier["roots"]],
        "aliases": list(tier.get("aliases") or []),
        "exists": any(root.is_dir() for root in tier["roots"]),
        "path_known": tier["path_known"],
        "recursive": tier["recursive"],
        "note": tier["note"],
        "instances": [_public_instance(item) for item in tier["loadable"]],
        "skipped": [_public_instance(item) for item in tier["skipped"]],
    }


def _build_tier(tier_spec: dict, project: Path | None, budget: dict) -> dict:
    """Resolve and read one documented tier.

    A root whose physical identity was already read by a higher tier (or an
    earlier root of this one) is recorded as an *alias* and not read again, so
    one physical skill cannot appear twice (SCOPE-7).
    """
    roots: list[Path] = []
    aliases: list[str] = []
    instances: list[dict] = []
    path_known = True
    recursive = False
    for root_spec in tier_spec["roots"]:
        if root_spec.get("path_known") is False:
            path_known = False
            continue
        recursive = recursive or bool(root_spec.get("recursive"))
        if root_spec.get("nested"):
            scanned = _nested_roots(project, str(root_spec.get("rel", "")), budget)
        else:
            resolved = _resolve_root(root_spec, project)
            scanned = [resolved] if resolved is not None else []
        roots.extend(scanned)
        for root in scanned:
            if not _scan_root_once(root, budget):
                aliases.append(str(root))
                continue
            remaining = MAX_INSTANCES - budget["instances"]
            if remaining <= 0:
                budget["truncated"] = True
                break
            found = _read_root(root, tier=tier_spec["id"], recursive=recursive,
                               scope=root_spec.get("scope"))
            instances.extend(found[:remaining])
            budget["instances"] += min(len(found), remaining)
    loadable, skipped = _classify(instances)
    return {
        "id": tier_spec["id"],
        "label": tier_spec["label"],
        "roots": roots,
        "aliases": aliases,
        "path_known": path_known,
        "recursive": recursive,
        "note": tier_spec.get("note"),
        "loadable": loadable,
        "skipped": skipped,
    }


def _build_tiers(spec: dict, project: Path | None, budget: dict) -> list[dict]:
    """Read every documented tier in order (highest precedence first)."""
    return [_build_tier(tier_spec, project, budget) for tier_spec in spec["tiers"]]


def _skipped_names(tiers: list[dict]) -> set[str]:
    return {
        str(item.get("name"))
        for tier in tiers
        for item in tier["skipped"]
        if item.get("name")
    }


def _resolve_ordered(skill: str, tiers: list[dict]) -> dict:
    """Resolve one skill name by walking the documented tier order."""
    for index, tier in enumerate(tiers):
        matches = [item for item in tier["loadable"] if item.get("name") == skill]
        if not matches:
            continue
        winner_physical = _physical(matches[0].get("path"))
        shadowed = [
            _public_instance(item)
            for lower in tiers[index + 1:]
            for item in lower["loadable"]
            if item.get("name") == skill
            # An alias of the winner is the winner, not a shadowed copy of it
            # (SCOPE-7): reporting it twice contradicts ADR-002 invariant 1.
            and _physical(item.get("path")) != winner_physical
        ]
        base = {
            "skill": skill,
            "winner_tier": tier["id"],
            "candidates": [_public_instance(item) for item in matches],
            "shadowed": shadowed,
        }
        if len(matches) > 1:
            base.update({
                "resolution": "ambiguous",
                "winner": None,
                "reason": f"tier '{tier['id']}' holds {len(matches)} copies of "
                "'{0}' and no order between its roots is recorded".format(skill),
            })
            return base
        base.update({
            "resolution": "resolved",
            "winner": _public_instance(matches[0]),
            "reason": f"the highest documented tier containing '{skill}' is "
            f"'{tier['id']}'",
        })
        return base
    return _no_instance(skill)


def _resolve_without_winner(skill: str, tiers: list[dict], outcome: str,
                            reason: str) -> dict:
    """Every visible instance loads; there is no winner to elect."""
    instances = [
        _public_instance(item)
        for tier in tiers
        for item in tier["loadable"]
        if item.get("name") == skill
    ]
    if not instances:
        return _no_instance(skill)
    return {
        "skill": skill,
        "resolution": outcome,
        "winner": None,
        "winner_tier": None,
        "candidates": instances,
        "shadowed": [],
        "reason": reason,
    }


def _no_instance(skill: str) -> dict:
    return {
        "skill": skill,
        "resolution": "no-instances",
        "winner": None,
        "winner_tier": None,
        "candidates": [],
        "shadowed": [],
        "reason": f"no loadable instance of '{skill}' in any documented root",
    }


def _overall(policy: str, skills: dict[str, dict]) -> str:
    """Summarise the per-skill resolutions without over-claiming (SCOPE-6).

    This used to return the policy's outcome -- ``resolved`` -- whenever no
    ambiguity was present, *including* when every skill was ``no-instances``.
    The top-level verdict then contradicted the entries beneath it: a report
    could say ``resolved`` while every skill said ``no-instances`` and no
    winner existed anywhere.
    """
    if not skills:
        return "no-instances"
    resolutions = {entry["resolution"] for entry in skills.values()}
    if resolutions == {"no-instances"}:
        return "no-instances"
    if policy != "ordered":
        return POLICY_OUTCOMES[policy]
    if resolutions == {"ambiguous"}:
        return "ambiguous"
    if "ambiguous" in resolutions:
        return "partially-ambiguous"
    if resolutions == {"both-load-only"}:
        # Every visible copy loads, but only through the both-load rule: no
        # ordered tier elected a winner, so "resolved" would over-claim.
        return "both-load-only"
    if "no-instances" in resolutions or "both-load-only" in resolutions:
        # Some skills resolve and others hold nothing (or only a nested copy):
        # neither plain "resolved" nor "no-instances" is true of the report as
        # a whole.
        return "partially-resolved"
    return POLICY_OUTCOMES[policy]


def _result(resolution: str, consumer: str | None = None, **extra) -> dict:
    payload = {
        "read_only": True,
        "persists_nothing": True,
        "resolution": resolution,
        "effective_state": UNRESOLVED,
        "policy_note": "derived at read time; effective_state stays 'unresolved' "
        "everywhere else",
    }
    if consumer is not None:
        payload["consumer"] = consumer
    payload.update(extra)
    return payload


#: Report keys whose *values* are filesystem paths.
_PATH_KEYS = frozenset({"project", "project_root", "roots", "path", "root"})
_PROJECT_KEYS = frozenset({"project", "project_root"})


def _redaction_key(key: str) -> str:
    """Return the active path key, or ``""`` when nothing is being redacted."""
    return key if key in _PATH_KEYS else ""


def _redact_value(key: str, value, roots: list[Path]):
    """Redact one report value that names a path outside the allowlisted roots.

    Redaction is key-driven and follows two rules: a path key keeps redacting
    the strings beneath it (a ``roots`` list, an instance's ``path``), and any
    other key carries no redaction.  A ``list`` keeps the surrounding path key
    because its elements are the paths; a ``dict`` does not, because its values
    carry their own keys.
    """
    if isinstance(value, str):
        if not key or value == "" or _under_any(roots, Path(value)):
            return value
        return REDACTED_PROJECT if key in _PROJECT_KEYS else REDACTED_ROOT
    if isinstance(value, list):
        return [_redact_value(key, item, roots) for item in value]
    if isinstance(value, dict):
        return {
            child: _redact_value(_redaction_key(child), item, roots)
            for child, item in value.items()
        }
    return value


def _redact_report(report: dict, roots: list[Path]) -> tuple[dict, bool]:
    """Replace every path outside *allowed_root* with a redaction marker.

    SEC-3: the report carries absolute paths for the user's real agent-skill
    roots and for every instance below them.  An unauthenticated HTTP caller
    must not learn the home directory, the OS username, the data directory, or
    the name/description/path inventory of skills installed for other tools.
    Returns ``(report, redacted_anything)``.
    """
    redacted = {
        key: _redact_value(_redaction_key(key), value, roots)
        for key, value in report.items()
    }
    return redacted, redacted != report


def _notes(spec: dict) -> list[str]:
    value = spec.get("notes")
    if isinstance(value, str):
        return [value]
    return list(value or ())


def _both_load(spec: dict, project: Path | None, budget: dict) -> dict[str, list[dict]]:
    """Collect the consumer's documented both-load instances, by skill name.

    SCOPE-16: the shared instance budget was enforced only in ``_build_tier``,
    so this scan could read past ``MAX_INSTANCES`` and the report then
    contradicted the module's own documented bound with no truncation warning.
    """
    config = spec.get("both_load")
    if not config:
        return {}
    collected: dict[str, list[dict]] = {}
    for root in _nested_roots(project, str(config["rel"]), budget):
        # Same physical-identity rule as the tiers (SCOPE-7): a nested root
        # that is an alias of one already read is not read a second time.
        if not _scan_root_once(root, budget):
            continue
        remaining = MAX_INSTANCES - budget["instances"]
        if remaining <= 0:
            budget["truncated"] = True
            break
        found = _read_root(root, tier="nested")[:remaining]
        budget["instances"] += len(found)
        for instance in found:
            loadable, _skipped = _classify([instance])
            for item in loadable:
                collected.setdefault(str(item["name"]), []).append(
                    _public_instance(item)
                )
    return collected


def _facade_warnings(spec: dict, budget: dict) -> list[str]:
    """Warn about facade-only instances, inside the shared read budget.

    SCOPE-16: this read was outside the budget too, so its instances were not
    counted against ``MAX_INSTANCES`` even though they were reported.
    """
    if not spec.get("facade_warning"):
        return []
    remaining = MAX_INSTANCES - budget["instances"]
    if remaining <= 0:
        budget["truncated"] = True
        return [spec["facade_warning"]]
    root = _facade_root(str(spec.get("facade_scope", "")))
    instances = _read_root(root, tier="facade", scope=spec.get("facade_scope"))[:remaining]
    budget["instances"] += len(instances)
    warnings = [spec["facade_warning"]]
    if instances:
        warnings.append(
            f"facade-only instances observed in scope '{spec.get('facade_scope')}': "
            f"{', '.join(sorted({str(item['name']) for item in instances}))}"
        )
    return warnings


def explain(consumer: str, project: str | Path | None = None, *,
            skill: str | None = None,
            allowed_root=None) -> dict:
    """Explain the effective instance for ``(consumer, project, skill)``.

    Returns a JSON-serialisable read-only report.  An unknown consumer or a
    missing project directory is never an exception and never a guess: it is an
    explicit ``unknown-consumer``/``missing-project`` result.

    *allowed_root* is the confinement boundary for path disclosure.  When it is
    set (the HTTP layer always sets it to the manager's data directory), any
    path in the report that lies outside it is redacted, a ``project`` outside
    it is not walked at all, and the caller is told why (SEC-2, SEC-3).  When
    it is ``None`` the caller is a local process that can already read those
    paths, so the report stays fully transparent.
    """
    allowed = _allowed_roots(allowed_root)
    if not isinstance(consumer, str) or not consumer.strip():
        return _result(
            "unknown-consumer",
            known_consumers=list(known_consumers()),
            reason="consumer must be a non-empty string",
        )
    key = consumer.strip().lower()
    spec = CONSUMERS.get(key)
    if spec is None:
        return _result(
            "unknown-consumer",
            consumer=key,
            known_consumers=list(known_consumers()),
            reason=f"'{consumer}' has no recorded precedence row; no order is guessed",
        )

    resolved_project: Path | None = None
    project_outside = False
    if project is not None:
        candidate = Path(str(project)).expanduser()
        if not candidate.is_dir():
            return _result(
                "missing-project",
                consumer=key,
                label=spec["label"],
                source=spec["source"],
                reason=f"project directory does not exist: {candidate}",
            )
        resolved_project = candidate.resolve()
        project_outside = bool(allowed) and not _under_any(allowed, resolved_project)

    if project_outside:
        # Do not walk a caller-chosen tree at all: no nested-root search, no
        # instance read, nothing that costs work or reveals a directory tree
        # (SEC-2 and SEC-3 together).
        return _result(
            "project-outside-managed-roots",
            consumer=key,
            label=spec["label"],
            source=spec["source"],
            policy=spec["policy"],
            project=None,
            project_supplied=True,
            skill=skill,
            skills={},
            skill_count=0,
            tiers=[],
            notes=_notes(spec),
            warnings=[
                "the requested project is outside this manager's data directory, "
                "so it was not walked and its paths are not reported",
                REDACTION_NOTE,
            ],
            unobservable_tiers=[],
            paths_redacted=True,
        )

    budget = {
        "instances": 0,
        "truncated": False,
        "entries": 0,
        "walk_truncated": False,
        "physical_roots": set(),
    }
    tiers = _build_tiers(spec, resolved_project, budget)
    policy = spec["policy"]
    outcome = POLICY_OUTCOMES[policy]
    both_load = _both_load(spec, resolved_project, budget)

    names = sorted(
        {
            str(item["name"])
            for tier in tiers
            for item in tier["loadable"] + tier["skipped"]
            if item.get("name")
        }
        | set(both_load)
    )
    if skill is not None:
        names = [name for name in names if name == skill]
        both_load = {name: value for name, value in both_load.items() if name == skill}

    reason = {
        "no-merge": "Codex documents an explicit no-merge policy: same-name skills "
        "do not merge and both can appear in selectors, so no winner is elected",
        "undocumented": f"{spec['label']} documents no same-name order across these "
        "roots, so no winner is elected",
    }.get(policy, "")

    skills: dict[str, dict] = {}
    for name in names:
        if policy == "ordered":
            entry = _resolve_ordered(name, tiers)
        else:
            entry = _resolve_without_winner(name, tiers, outcome, reason)
        entry["also_loads"] = both_load.get(name, [])
        entry["also_loads_reason"] = (
            str(spec["both_load"]["reason"]) if both_load.get(name) else None
        )
        if entry["resolution"] == "no-instances" and entry["also_loads"]:
            # SCOPE-6: the reason used to read "no loadable instance ... in any
            # documented root" while the entry's own also_loads list held that
            # very loadable instance.  A nested copy loads through the
            # documented both-load rule, so the honest answer is that it is the
            # only loadable copy -- there is simply no ordered tier holding it.
            entry.update({
                "resolution": "both-load-only",
                "candidates": list(entry["also_loads"]),
                "reason": f"no documented tier holds '{name}'; the nested copy "
                "loads through the documented both-load rule, so no ordered "
                "winner is elected",
            })
        elif entry["resolution"] == "no-instances" and name in _skipped_names(tiers):
            entry["reason"] += " (only disabled or invalid copies were found)"
        skills[name] = entry

    warnings = _facade_warnings(spec, budget)
    for tier in tiers:
        if not tier["path_known"]:
            warnings.append(
                f"tier '{tier['id']}' is documented but has no readable path in this "
                "facade; a lower-tier winner may be provisional"
            )
    if budget["truncated"]:
        warnings.append(f"read truncated at {MAX_INSTANCES} instances")
    if budget.get("walk_truncated"):
        warnings.append(
            f"the nested-root search stopped after {MAX_WALK_ENTRIES} directory "
            "entries or " + str(MAX_WALK_DEPTH) + " levels"
        )

    report = _result(
        _overall(policy, skills),
        consumer=key,
        label=spec["label"],
        source=spec["source"],
        policy=policy,
        project=str(resolved_project) if resolved_project else None,
        project_supplied=project is not None,
        skill=skill,
        skills=skills,
        skill_count=len(skills),
        tiers=[_tier_report(tier) for tier in tiers],
        notes=_notes(spec),
        warnings=warnings,
        unobservable_tiers=[tier["id"] for tier in tiers if not tier["path_known"]],
    )
    if not allowed:
        return report
    report, changed = _redact_report(report, allowed)
    if changed:
        report["paths_redacted"] = True
        report["warnings"] = list(report.get("warnings") or []) + [REDACTION_NOTE]
    return report

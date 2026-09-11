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

from pathlib import Path

from .loader import scan_dir

#: Bounds: a diagnostic must never walk an unbounded tree. ``MAX_ROOTS`` caps
#: the nested-root search and ``MAX_INSTANCES`` the instances read overall.
MAX_ROOTS = 32
MAX_INSTANCES = 500

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


def _nested_roots(project: Path | None, rel: str) -> list[Path]:
    """Project-relative roots below the project root (nested discovery)."""
    if project is None or not project.is_dir():
        return []
    top = project / rel
    found: list[Path] = []
    try:
        for candidate in project.rglob(rel):
            if len(found) >= MAX_ROOTS:
                break
            if candidate.is_dir() and candidate != top:
                found.append(candidate)
    except OSError:
        return sorted(found)
    return sorted(found)


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
        "exists": any(root.is_dir() for root in tier["roots"]),
        "path_known": tier["path_known"],
        "recursive": tier["recursive"],
        "note": tier["note"],
        "instances": [_public_instance(item) for item in tier["loadable"]],
        "skipped": [_public_instance(item) for item in tier["skipped"]],
    }


def _build_tier(tier_spec: dict, project: Path | None, budget: dict) -> dict:
    """Resolve and read one documented tier."""
    roots: list[Path] = []
    instances: list[dict] = []
    path_known = True
    recursive = False
    for root_spec in tier_spec["roots"]:
        if root_spec.get("path_known") is False:
            path_known = False
            continue
        recursive = recursive or bool(root_spec.get("recursive"))
        if root_spec.get("nested"):
            scanned = _nested_roots(project, str(root_spec.get("rel", "")))
        else:
            resolved = _resolve_root(root_spec, project)
            scanned = [resolved] if resolved is not None else []
        roots.extend(scanned)
        for root in scanned:
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
        shadowed = [
            _public_instance(item)
            for lower in tiers[index + 1:]
            for item in lower["loadable"]
            if item.get("name") == skill
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
    if not skills:
        return "no-instances"
    if policy != "ordered":
        return POLICY_OUTCOMES[policy]
    resolutions = {entry["resolution"] for entry in skills.values()}
    if resolutions == {"ambiguous"}:
        return "ambiguous"
    if "ambiguous" in resolutions:
        return "partially-ambiguous"
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


def _notes(spec: dict) -> list[str]:
    value = spec.get("notes")
    if isinstance(value, str):
        return [value]
    return list(value or ())


def _both_load(spec: dict, project: Path | None) -> dict[str, list[dict]]:
    """Collect the consumer's documented both-load instances, by skill name."""
    config = spec.get("both_load")
    if not config:
        return {}
    collected: dict[str, list[dict]] = {}
    for root in _nested_roots(project, str(config["rel"])):
        for instance in _read_root(root, tier="nested"):
            loadable, _skipped = _classify([instance])
            for item in loadable:
                collected.setdefault(str(item["name"]), []).append(
                    _public_instance(item)
                )
    return collected


def _facade_warnings(spec: dict) -> list[str]:
    if not spec.get("facade_warning"):
        return []
    root = _facade_root(str(spec.get("facade_scope", "")))
    instances = _read_root(root, tier="facade", scope=spec.get("facade_scope"))
    warnings = [spec["facade_warning"]]
    if instances:
        warnings.append(
            f"facade-only instances observed at {root}: "
            f"{', '.join(sorted({str(item['name']) for item in instances}))}"
        )
    return warnings


def explain(consumer: str, project: str | Path | None = None, *,
            skill: str | None = None) -> dict:
    """Explain the effective instance for ``(consumer, project, skill)``.

    Returns a JSON-serialisable read-only report.  An unknown consumer or a
    missing project directory is never an exception and never a guess: it is an
    explicit ``unknown-consumer``/``missing-project`` result.
    """
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

    budget = {"instances": 0, "truncated": False}
    tiers = _build_tiers(spec, resolved_project, budget)
    policy = spec["policy"]
    outcome = POLICY_OUTCOMES[policy]
    both_load = _both_load(spec, resolved_project)

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
        if entry["resolution"] == "no-instances" and name in _skipped_names(tiers):
            entry["reason"] += " (only disabled or invalid copies were found)"
        skills[name] = entry

    warnings = _facade_warnings(spec)
    for tier in tiers:
        if not tier["path_known"]:
            warnings.append(
                f"tier '{tier['id']}' is documented but has no readable path in this "
                "facade; a lower-tier winner may be provisional"
            )
    if budget["truncated"]:
        warnings.append(f"read truncated at {MAX_INSTANCES} instances")

    return _result(
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

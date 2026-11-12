"""Private CLI command handlers.

The parser lives in :mod:`skillsmgr.cli_parser`; output helpers live in
:mod:`skillsmgr.cli_output`. This module owns the per-command behavior behind
the ``cmd_*`` names the parser wires. ``skillsmgr.cli`` re-exports these names
as compatibility adapters so existing callers keep working.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess  # nosec B404 - reviewed editor and allowlisted installer calls use list argv.
import sys
from pathlib import Path

from . import path_safety
from . import colors
from . import doctor, effective, evals, install, paths, scopes, source_update
from .documents import document_path
from . import templates as templates_mod
#: CLI-3: untrusted skill fields (description, category, notes) come from
#: imported archives and from directories other tools wrote, so every printed
#: field passes through ``sanitize_text`` (as ``_display``).
from .cli_output import (
    err as _err,
    print_json as _print_json,
    render_table as _render_table,
    sanitize_text as _display,
    truncate as _truncate,
)
from .store import Store, StoreError
from .validator import validate_skill, validate_skill_name
from .external_scan import scan_options
from .store import list_snapshots
from .tokens import aggregate, estimate, format_tokens, window_name
from .cli_ai import cmd_ai

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPT = 130


#: A metadata key is emitted as a bare frontmatter mapping key, so it may not
#: carry a control character (CLI-2: a key containing a newline wrote a document
#: this tool cannot parse, and the next edit then emitted a second frontmatter
#: block -- exit 0 throughout, with ``doctor`` reporting ok).
def parse_metadata(pairs: list[str] | None) -> dict | None:
    """Parse repeated ``KEY=VALUE`` CLI metadata flags."""
    if not pairs:
        return None
    data = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"metadata must be KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"metadata key must not be empty, got {pair!r}")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in key):
            raise ValueError(
                f"metadata key must not contain a control character, got {key!r}"
            )
        data[key] = value
    return data


def read_body(args) -> str | None:
    """Return ``--body``/``--body-file`` content for create/edit commands."""
    if args.body is not None and args.body_file is not None:
        raise ValueError("use only one of --body or --body-file")
    if args.body_file is not None:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body


def skill_md_path(store: Store, name: str) -> Path:
    """Locate the on-disk SKILL.md (or disabled twin) for ``name``."""
    record = store.get(name)
    if record["path"] is None:
        raise StoreError(f"skill '{name}' has no directory on disk")
    document = document_path(Path(record["path"]))
    if document is not None:
        return document
    raise StoreError(f"skill '{name}' has no SKILL.md (or SKILL.md.disabled)")


def scope_from_args(args) -> str:
    """Return the normalized ``--scope`` value for a parsed command."""
    return (getattr(args, "scope", None) or "global").strip() or "global"


def validate_cli_names(args) -> None:
    """Reject invalid skill names before handlers construct paths or stores."""
    command = getattr(args, "command", "")
    names: list[str] = []
    if command in {
        "create",
        "view",
        "edit",
        "open",
        "remove",
        "rm",
        "disable",
        "enable",
        "restore",
        "sync",
    }:
        names.append(getattr(args, "name", ""))
    elif command == "add" and getattr(args, "name", None):
        names.append(args.name)
    elif command == "history" and getattr(args, "name", None):
        names.append(args.name)
    elif command == "tokens" and getattr(args, "name", None):
        names.append(args.name)
    elif command == "update" and getattr(args, "name", None):
        names.append(args.name)
    elif command == "validate" and not getattr(args, "path", None):
        names.extend(getattr(args, "names", []) or [])
    elif command == "trash" and getattr(args, "trash_command", None) == "restore":
        names.append(getattr(args, "name", ""))

    for raw_name in names:
        try:
            validate_skill_name(str(raw_name).strip())
        except ValueError as exc:
            raise StoreError(str(exc)) from exc


def validate_cli_combinations(args) -> None:
    """Reject parsed flag combinations whose values would otherwise be ignored."""
    command = getattr(args, "command", "")
    if command == "validate":
        names = getattr(args, "names", []) or []
        path = getattr(args, "path", None)
        if names and getattr(args, "all", False):
            message = "validate NAME arguments cannot be combined with --all"
            if getattr(args, "evals_run", None):
                message += "; --evals-run applies to exactly one skill"
            raise StoreError(message)
        if names and path is not None:
            raise StoreError("validate NAME arguments cannot be combined with --path")
        if getattr(args, "all", False) and path is not None:
            raise StoreError("validate --all cannot be combined with --path")
        if getattr(args, "workspace", None) and not (
            getattr(args, "evals", False) or getattr(args, "evals_run", None)
        ):
            raise StoreError("validate --workspace requires --evals or --evals-run")
    elif command == "tokens":
        if getattr(args, "name", None) and getattr(args, "text", None) is not None:
            raise StoreError("tokens NAME cannot be combined with --text")
    elif command == "doctor":
        if getattr(args, "hygiene", False) and getattr(args, "explain", None):
            raise StoreError("doctor --hygiene cannot be combined with --explain")
    elif command == "install":
        operation = any(
            getattr(args, flag, False)
            for flag in ("browse", "curated", "fetch")
        ) or getattr(args, "search", None) is not None
        if operation and getattr(args, "preview", False):
            raise StoreError("registry operations cannot be combined with --preview")
        if operation and getattr(args, "dry_run", False):
            raise StoreError("registry operations cannot be combined with --dry-run")
        if operation and getattr(args, "trust_confirmed", False) and not getattr(args, "fetch", False):
            raise StoreError("--trust-confirmed applies to --preview or --fetch only")
        if operation and getattr(args, "runner", "npx") != "npx":
            raise StoreError("registry operations cannot be combined with --runner")
        if operation and getattr(args, "agent", None):
            raise StoreError("registry operations cannot be combined with --agent")
        if operation and getattr(args, "skill", None):
            raise StoreError("registry operations cannot be combined with --skill")
        if operation and getattr(args, "copy", False):
            raise StoreError("registry operations cannot be combined with --copy")
        if operation and getattr(args, "list_only", False):
            raise StoreError("registry operations cannot be combined with --list-only")
        if getattr(args, "review", None) and not getattr(args, "fetch", False):
            raise StoreError("install --review requires --fetch")
        if getattr(args, "review", None) and getattr(args, "source", None):
            raise StoreError("install --fetch --review does not accept a source; use the review id")
        if getattr(args, "trust_confirmed", False) and not (
            getattr(args, "preview", False) or getattr(args, "fetch", False)
        ):
            raise StoreError("install --trust-confirmed requires --preview or --fetch")
        if getattr(args, "registry_hash", None) is not None and not (
            getattr(args, "preview", False) or getattr(args, "fetch", False)
        ):
            raise StoreError("install --registry-hash requires --preview or --fetch")
        if operation and getattr(args, "curated", False) and getattr(args, "source", None):
            raise StoreError("install --curated does not accept a source")
        if operation and getattr(args, "search", None) is not None and getattr(args, "source", None):
            raise StoreError("install --search does not accept a source")
        if operation and getattr(args, "browse", False) and getattr(args, "source", None):
            raise StoreError("install --browse does not accept a source")
        if operation and not getattr(args, "fetch", False) and getattr(args, "registry_hash", None) is not None:
            raise StoreError("--registry-hash requires --fetch or --preview")
        if getattr(args, "fetch", False) and not getattr(args, "review", None) and not getattr(args, "source", None):
            raise StoreError("install --fetch requires a registry skill id")
        if getattr(args, "review", None) and not getattr(args, "trust_confirmed", False):
            raise StoreError("install --fetch --review requires --trust-confirmed after reviewing the source")
    elif command == "update":
        if scope_from_args(args) == "all":
            raise StoreError("update mutations cannot use --scope all; choose one exact scope")


# Commands that only read. They never create the data layout, the index file
# or the schema, so `doctor` can report a lost index instead of rebuilding it
# before it looks.
_READ_ONLY_COMMANDS = frozenset(
    {"list", "ls", "view", "search", "stats", "doctor", "history", "scopes", "tokens", "ai"}
)


def _is_read_only(args) -> bool:
    return getattr(args, "command", None) in _READ_ONLY_COMMANDS


def _ensure_index_for(store: Store, args) -> None:
    """Bootstrap the index, unless this command only reads.

    A read command must not bootstrap: `skills-mgr doctor` recreating the index
    before it audits is how a lost index could never be reported -- the exact
    "a read that repairs the disk on its way to answering" defect docs/24 §D3-4
    closed on the web side.  Reads handle an absent index themselves
    (docs/04-store-api.md), so nothing needs the bootstrap here.
    """
    if not _is_read_only(args):
        store.init_db()


def make_store(args) -> Store:
    """Build a Store for parsed CLI args, honoring ``--data-dir``/color flags."""
    if args.data_dir:
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(args.data_dir).expanduser())
    if args.color == "always":
        colors.COLORS.enabled = True
    elif args.color == "never":
        colors.COLORS.enabled = False
    store = Store()
    _ensure_index_for(store, args)
    return store


def cmd_init(args, store: Store) -> int:
    store.init_db()
    if args.json:
        _print_json({"data_dir": str(store.data_dir), "ok": True})
    else:
        print(f"initialized {store.data_dir}")
    return EXIT_OK


def cmd_list(args, store: Store) -> int:
    scope = scope_from_args(args)
    if scope == "all":
        rows = scopes.list_all()
    elif scope != "global":
        rows = scopes.scan_scope(scope)
    else:
        rows = store.list()
    # Add scope label for all view.
    show_scope = scope == "all"
    if args.disabled:
        rows = [row for row in rows if row["disabled"]]
    if args.category:
        rows = [row for row in rows if row["category"] == args.category]
    if args.json:
        _print_json(rows)
        return EXIT_OK
    if not rows:
        print("no skills installed")
        return EXIT_OK
    header = ["SCOPE", "NAME", "STATUS", "CATEGORY", "DESCRIPTION"] if show_scope else ["NAME", "STATUS", "CATEGORY", "DESCRIPTION"]
    table = []
    for row in rows:
        base = [
            row["name"],
            "disabled" if row["disabled"] else "active",
            row["category"] or "-",
            _truncate(row["description"] or "", 50),
        ]
        if show_scope:
            base = [row.get("scope", scope)] + base
        table.append(base)
    print(_render_table([header] + table))
    return EXIT_OK


def cmd_create(args, store: Store) -> int:
    try:
        result = store.create(
            args.name,
            args.description,
            license=args.license,
            category=args.category,
            compatibility=args.compatibility,
            version=args.version,
            allowed_tools=args.allowed_tools,
            metadata_extra=parse_metadata(args.metadata),
            body=read_body(args),
        )
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    if args.json:
        _print_json(result)
    else:
        print(f"created {colors.COLORS.green(result['name'])} at {result['path']}")
    return EXIT_OK


def cmd_add(args, store: Store) -> int:
    result = store.add(args.path, name=args.name)
    if args.json:
        _print_json(result)
    else:
        print(f"installed {colors.COLORS.green(result['name'])} from {args.path}")
    return EXIT_OK


def cmd_view(args, store: Store) -> int:
    if args.raw and args.json:
        raise StoreError("cannot combine --raw and --json")
    scope = scope_from_args(args)
    if scope != "global":
        if args.raw:
            print(scopes.get_raw(scope, args.name), end="")
            return EXIT_OK
        record = scopes.get_skill(scope, args.name)
        if args.json:
            _print_json(record)
            return EXIT_OK
        fields = [
            ("scope", record.get("scope", scope)),
            ("name", record["name"]),
            ("status", "disabled" if record["disabled"] else "active"),
            ("category", record["category"] or "-"),
            ("license", record["license"] or "-"),
            ("version", record["version"] or "-"),
            ("description", record["description"] or "-"),
            ("path", record["path"] or "-"),
        ]
        for key, value in fields:
            print(f"{colors.COLORS.bold(key + ':')} {_display(str(value))}")
        return EXIT_OK
    record = store.get(args.name)
    if args.raw:
        print(skill_md_path(store, args.name).read_text(encoding="utf-8"), end="")
        return EXIT_OK
    if args.json:
        _print_json(record)
        return EXIT_OK
    fields = [
        ("name", record["name"]),
        ("status", "disabled" if record["disabled"] else "active"),
        ("category", record["category"] or "-"),
        ("license", record["license"] or "-"),
        ("version", record["version"] or "-"),
        ("description", record["description"] or "-"),
        ("path", record["path"] or "-"),
        ("updated", record["updated_at"] or "-"),
    ]
    for key, value in fields:
        print(f"{colors.COLORS.bold(key + ':')} {_display(str(value))}")
    return EXIT_OK


def cmd_edit(args, store: Store) -> int:
    try:
        result = store.edit(
            args.name,
            description=args.description,
            license=args.license,
            category=args.category,
            compatibility=args.compatibility,
            version=args.version,
            allowed_tools=args.allowed_tools,
            metadata_extra=parse_metadata(args.metadata),
            body=read_body(args),
        )
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    if args.json:
        _print_json(result)
    elif result.get("changed"):
        print(f"updated {colors.COLORS.green(args.name)}")
    else:
        print(f"no changes for {args.name}")
    return EXIT_OK


def cmd_open(args, store: Store) -> int:
    md_path = skill_md_path(store, args.name)
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        raise StoreError("set $EDITOR (or $VISUAL) to use 'open'")
    status = subprocess.call(  # nosec B603 - explicit user-authorized editor, list argv, shell=False.
        shlex.split(editor) + [str(md_path)]
    )
    if status != 0:
        raise StoreError(f"editor exited with status {status}")
    store.resync()
    print(f"resynced index after editing {args.name}")
    return EXIT_OK


def cmd_remove(args, store: Store) -> int:
    result = store.remove(args.name, purge=args.purge)
    if args.json:
        _print_json(result)
    elif result["action"] == "purged":
        print(f"purged {args.name}")
    else:
        print(f"trashed {args.name} (restore with 'skills-mgr restore {args.name}')")
    return EXIT_OK


def cmd_disable(args, store: Store) -> int:
    store.disable(args.name)
    if args.json:
        _print_json({"name": args.name, "disabled": True})
    else:
        print(f"disabled {colors.COLORS.yellow(args.name)}")
    return EXIT_OK


def cmd_enable(args, store: Store) -> int:
    store.enable(args.name)
    if args.json:
        _print_json({"name": args.name, "disabled": False})
    else:
        print(f"enabled {colors.COLORS.green(args.name)}")
    return EXIT_OK


def cmd_validate(args, store: Store) -> int:
    targets = []
    if args.path:
        root = Path(args.path).expanduser()
        targets.append((root.name, root))
    elif args.all:
        for name in sorted(p.name for p in paths.skills_dir().iterdir() if p.is_dir()):
            try:
                root = path_safety.safe_skill_path(paths.skills_dir(), name)
            except ValueError:
                root = None
            targets.append((name, root))
    else:
        for name in args.names:
            record = store.get(name)
            targets.append((name, Path(record["path"]) if record["path"] else None))
    if not targets:
        raise StoreError("no skills to validate; pass NAMES, --all, or --path")
    evals_run = getattr(args, "evals_run", None)
    want_evals = bool(getattr(args, "evals", False) or evals_run)
    if evals_run and len(targets) != 1:
        raise StoreError("--evals-run applies to exactly one skill; pass a single NAME or --path")
    runs_document = _load_eval_runs(evals_run) if evals_run else None
    results = []
    any_errors = False
    for name, root in targets:
        if root is None or not root.is_dir():
            results.append(
                {
                    "name": name,
                    "valid": False,
                    "errors": [f"skill directory not found: {root}"],
                    "warnings": [],
                }
            )
            any_errors = True
            continue
        result = validate_skill(name, root)
        entry = {
            "name": name,
            "valid": result.valid,
            "errors": [issue.message for issue in result.errors],
            "warnings": [issue.message for issue in result.warnings],
        }
        if want_evals:
            entry["evals"] = _eval_report(name, root, store, args, runs_document)
        results.append(entry)
        if not result.valid:
            any_errors = True
    if args.json:
        _print_json({"valid": not any_errors, "skills": results})
        return EXIT_OK if not any_errors else EXIT_ERROR
    for entry in results:
        status = colors.COLORS.green("ok") if entry["valid"] else colors.COLORS.red("invalid")
        print(f"{entry['name']}: {status}")
        for message in entry["warnings"]:
            print(f"  {colors.COLORS.yellow('warn')}  {message}")
        for message in entry["errors"]:
            print(f"  {colors.COLORS.red('error')} {message}")
        _print_eval_report(entry.get("evals"))
    return EXIT_OK if not any_errors else EXIT_ERROR


def _load_eval_runs(path_text: str) -> dict:
    """Read an eval runs document (``{iteration, runs}`` or a bare run list)."""
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise StoreError(f"eval runs file not found: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise StoreError(f"eval runs file is not valid JSON: {exc}") from exc
    return _eval_runs_document(document)


def _eval_runs_document(document) -> dict:
    """Normalize the two accepted runs-file shapes before recording."""
    if isinstance(document, list):
        return {"iteration": 1, "runs": document}
    if not isinstance(document, dict):
        raise StoreError("eval runs file must contain an object or a list")
    iteration = document.get("iteration", 1)
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
        raise StoreError("eval runs iteration must be a positive integer")
    if not isinstance(document.get("runs"), list):
        raise StoreError("eval runs must be a list")
    return {"iteration": iteration, "runs": document.get("runs")}


def _eval_workspace(name: str, root: Path, store: Store, args) -> Path:
    """Resolve the eval workspace: explicit override, store default, or beside."""
    override = getattr(args, "workspace", None)
    if override:
        workspace = Path(override).expanduser()
    elif getattr(args, "path", None):
        workspace = evals.workspace_for_dir(root, store.data_dir, name)
    else:
        workspace = evals.workspace_for(store.data_dir, name)
    return evals.ensure_workspace_outside(workspace, store.data_dir)


def _eval_report(name: str, root: Path, store: Store, args, runs_document) -> dict:
    """Build the advisory eval report for one validated skill directory."""
    workspace = _eval_workspace(name, root, store, args)
    if runs_document is None:
        report = evals.eval_report(root, workspace, name)
    else:
        report = evals.eval_report(
            root, workspace, name, runs=runs_document["runs"], iteration=runs_document["iteration"]
        )
    report["workspace_override"] = bool(getattr(args, "workspace", None))
    return report


def _print_eval_report(report: dict | None) -> None:
    """Print the advisory eval harness block for one skill."""
    if not report:
        return
    if not report.get("present"):
        print("  evals         no evals/evals.json (advisory; add one to grade this skill)")
        return
    print(f"  evals         {len(report['cases'])} case(s) in evals/evals.json (advisory-only)")
    for issue in report["issues"]:
        level = issue["level"]
        label = colors.COLORS.red("error") if level == "error" else colors.COLORS.yellow("warn")
        print(f"  {label}{' ' * (13 - len(level))} {issue['message']}")
    recording = report.get("recording")
    if recording:
        variants = recording["benchmark"]["variants"]
        summary = ", ".join(
            f"{variant} {bucket['cases_passed']}/{bucket['graded']} case(s) "
            f"({bucket['assertions_passed']}/{bucket['assertions_total']} assertions)"
            for variant, bucket in sorted(variants.items())
        ) or "no graded runs"
        print(f"  eval runs     {summary} (advisory; scores never block installs)")
        ungraded = recording["benchmark"]["ungraded_cases"]
        if ungraded:
            warn = colors.COLORS.yellow("warn")
            print(f"  {warn}{' ' * 9} {ungraded} case(s) have no assertions yet; add them after the first run")
        delta = recording["benchmark"]["delta"]
        if delta is not None:
            print(f"  eval delta    with_skill - without_skill = {delta:+.4f} (case pass rate)")
        print(f"  workspace     {recording['workspace']} ({len(recording['written'])} file(s) written)")
    else:
        print(f"  workspace     {report['workspace']}/iteration-N/eval-<slug>/with_skill|without_skill")


def search_output_row(match: dict, scope: str) -> dict:
    """Keep the historical CLI row shape for global and merged results."""
    if scope == "all":
        return dict(match)
    return {key: value for key, value in match.items() if key not in ("scope", "scope_label")}


def cmd_search(args, store: Store) -> int:
    if args.limit is not None and args.limit < 1:
        raise StoreError("--limit must be a positive integer")
    scope = scope_from_args(args)
    ranked = [
        (search_output_row(row, scope), score)
        for row, score in scopes.search_ranked(args.term, scope_id=scope, store=store)
    ]
    if args.limit:
        ranked = ranked[: args.limit]
    if args.json:
        _print_json([record for record, _ in ranked])
        return EXIT_OK
    if not ranked:
        print(f"no matches for {args.term!r}")
        return EXIT_OK
    show_scope = scope == "all"
    header = ["SCOPE", "NAME", "CATEGORY", "DESCRIPTION", "SCORE"] if show_scope else ["NAME", "CATEGORY", "DESCRIPTION", "SCORE"]
    table = []
    for record, score in ranked:
        base = [
            record["name"],
            record["category"] or "-",
            _truncate(record["description"] or "", 45),
            str(score),
        ]
        if show_scope:
            base = [record.get("scope", scope)] + base
        table.append(base)
    print(_render_table([header] + table))
    return EXIT_OK


def cmd_import(args, store: Store) -> int:
    result = store.import_(args.archive, force=args.force, full=args.full)
    if args.json:
        _print_json(result)
    else:
        print(
            f"imported {result['imported']}, skipped {result['skipped']} "
            f"from {result['source']}"
        )
        if "restored_trash" in result:
            print(f"trash restored: {result['restored_trash']}, templates restored: {result['restored_templates']}, skipped: {result['skipped_full']}")
    return EXIT_OK


def cmd_export(args, store: Store) -> int:
    result = store.export(args.dest, full=args.full)
    if args.json:
        _print_json({"path": str(result)})
    else:
        print(f"{'full export' if args.full else 'exported skills'} to {result}")
    return EXIT_OK


def cmd_backup(args, store: Store) -> int:
    result = store.backup(args.dest, full=args.full)
    if args.json:
        _print_json({"path": str(result)})
    else:
        print(f"backup written to {result}")
    return EXIT_OK


def cmd_restore(args, store: Store) -> int:
    snapshot = getattr(args, "snapshot", None)
    if snapshot:
        scope = scope_from_args(args)
        result = scopes.restore_snapshot(scope, args.name, snapshot)
        if args.json:
            _print_json(result)
        else:
            print(f"rolled back {colors.COLORS.green(result['name'])} to snapshot {snapshot} (scope: {result.get('scope', 'global')})")
        return EXIT_OK
    result = store.restore(args.name)
    if args.json:
        _print_json(result)
    else:
        print(
            f"restored {colors.COLORS.green(result['name'])} "
            f"from {result['restored_from']}"
        )
    return EXIT_OK


def _render_lockfile_text(lockfiles: dict | None) -> None:
    """Print one bounded summary line plus any unusable lock state."""
    lockfiles = lockfiles or {}
    summary = lockfiles.get("summary") or {}
    if summary:
        print(
            "  lockfiles: declared {declared}; present {present}; missing {missing}; "
            "hash match {match}, differs {differs}, unverifiable {unverifiable}, "
            "not recorded {not_recorded}".format(**summary)
        )
    for key in ("global", "project"):
        lock = lockfiles.get(key) or {}
        if lock.get("state") and lock.get("state") != "ok":
            print(
                f"    {_display(str(key))} lock: {_display(str(lock.get('state')))} "
                f"({_display(str(lock.get('reason', '')))})"
            )
    if lockfiles.get("undeclared", {}).get("names"):
        print(f"    undeclared installed skills: {len(lockfiles['undeclared']['names'])}")
    for signal in lockfiles.get("unavailable_signals", []):
        print(f"    unavailable {_display(str(signal.get('signal', '')))}: {_display(str(signal.get('explanation', '')))}")


def _render_claude_listing_text(section: dict | None) -> None:
    """One bounded summary line for the Claude Code listing-budget estimate."""
    if not section:
        return
    chars = int(section.get("listing_chars", 0) or 0)
    budget = (section.get("budget") or {}).get("budget_chars_estimate") or 0
    candidates = (section.get("name_only_candidates") or {}).get("total", 0)
    if section.get("status") == "unknown":
        print(
            f"  Claude Code listing: {chars:,} chars; budget unknown "
            f"(partial settings evidence); {candidates} name-only candidates"
        )
        return
    print(
        f"  Claude Code listing: {chars:,} chars vs ~{budget:,} budget (estimate); "
        f"{candidates} name-only candidates"
    )


def _render_agents_bridge_text(section: dict | None) -> None:
    """One summary line for skills Claude Code cannot see (docs/29 H2)."""
    if not section or section.get("state") != "observed":
        return
    total = int(section.get("missing_total", 0) or 0)
    if not total:
        return
    noun = "skill that is" if total == 1 else "skills that are"
    copy = next((r.get("command") for r in section.get("remedies", []) if r.get("kind") == "copy"), "")
    print(
        f"  Claude Code cannot see {total} {noun} only in ~/.agents/skills "
        f"(copy it with: {_display(str(copy))})"
    )


def _render_hygiene_text(report: dict) -> None:
    """Render report evidence through the terminal sanitization seam."""
    summary = report.get("summary", {})
    print(colors.COLORS.bold("Skill Hygiene Report"))
    print(f"  scope: {_display(str(report.get('scope', '-')))}")
    print(
        "  observed records: {observed_records}; physical instances: {physical_instances}; "
        "logical names: {logical_names}".format(**summary)
    )
    print(
        "  findings: {finding_count} (errors {errors}, warnings {warnings}, info {informational}, "
        "unavailable {unavailable})".format(**summary)
    )
    _render_lockfile_text(report.get("lockfiles"))
    _render_claude_listing_text(report.get("claude_listing"))
    _render_agents_bridge_text(report.get("agents_bridge"))
    if summary.get("findings_truncated"):
        print("  findings returned are bounded; inspect the JSON limits/degraded evidence")
    for finding in report.get("findings", []):
        print(
            f"  [{_display(str(finding.get('severity', 'info')))}] "
            f"{_display(str(finding.get('category', '')))}: "
            f"{_display(str(finding.get('title', '')))}"
        )
        print(f"    {_display(str(finding.get('explanation', '')))}")
        for instance in finding.get("instances", []):
            location = instance.get("physical_path") or instance.get("path") or "path unavailable"
            print(
                f"    - {_display(str(instance.get('scope', '')))} / "
                f"{_display(str(instance.get('name', '')))}: {_display(str(location))}"
            )
        print(f"    follow-up: {_display(str(finding.get('recommendation', '')))}")
    if report.get("largest_instances"):
        print("  context hotspots:")
        for item in report["largest_instances"]:
            location = item.get("physical_path") or item.get("path") or "path unavailable"
            print(
                f"    {_display(str(item.get('name', '')))}: {item.get('tokens', 0)} tokens "
                f"({_display(str(location))})"
            )
    if report.get("degraded"):
        print("  degraded evidence:")
        for item in report["degraded"]:
            print(f"    {_display(str(item.get('section', 'scan')))}: {_display(str(item.get('reason', '')))}")
    if report.get("unavailable_signals"):
        print("  unavailable evidence:")
        for item in report["unavailable_signals"]:
            print(
                f"    {_display(str(item.get('signal', 'signal')))}: "
                f"{_display(str(item.get('explanation', 'not observed')))}"
            )


def _print_doctor_index_report(report: dict) -> None:
    """Show what to do about the index, not only that something is wrong.

    A ``repair`` line with no reader is a promise nobody keeps, and "database
    integrity check failed" is the wrong wording for an index that was never
    built.
    """
    for line in report.get("repair") or []:
        print(f"  repair: {line}")
    integrity = report.get("db_integrity")
    if integrity and integrity not in ("ok", "unindexed"):
        print(f"  database integrity check failed: {integrity}")


def cmd_doctor(args, store: Store) -> int:
    scope = scope_from_args(args)
    doctor.require_scope(scope)
    explain_consumer = getattr(args, "explain", None)
    if explain_consumer:
        return _cmd_doctor_explain(args, explain_consumer)
    hygiene = bool(getattr(args, "hygiene", False))
    report = doctor.doctor_report(store, scope, hygiene=hygiene)
    if args.json:
        _print_json(report)
        return EXIT_OK
    if report.get("ok"):
        if scope != "global":
            print(f"{colors.COLORS.green('ok:')} {scope} filesystem is healthy")
        else:
            print(f"{colors.COLORS.green('ok:')} filesystem and database are consistent")
    else:
        print(f"{colors.COLORS.yellow('issues found:')}" + (f" ({scope})" if scope != "global" else ""))
    if report.get("orphan_dirs"):
        print(f"  {len(report['orphan_dirs'])} unindexed skill directories")
    if report.get("stale_rows"):
        print(f"  {len(report['stale_rows'])} database rows without files")
    _print_doctor_document_issues(report)
    _print_doctor_index_report(report)
    # Also show scope summary when --scope all.
    if scope == "all":
        for s in report["scopes"]:
            print(f"  {s['label']} ({s['id']}): {s['count']} skills at {s['path']}")
        if report["duplicates"]:
            print(f"  {len(report['duplicates'])} skill name(s) present in multiple scopes:")
            for d in report["duplicates"]:
                flag = " (descriptions differ)" if d["descriptions_differ"] else ""
                print(f"    {d['name']}: {', '.join(d['scopes'])}{flag}")
        if any(item.get("section") == "scopes/duplicates" for item in report.get("degraded", [])):
            print("  scope and duplicate summary unavailable; inspect diagnostics", file=sys.stderr)
    if hygiene:
        _render_hygiene_text(report["hygiene"])
        return EXIT_OK
    return EXIT_OK if report.get("ok") else EXIT_ERROR


def _print_doctor_document_issues(report: dict) -> None:
    if report.get("malformed_documents"):
        names = ", ".join(_display(name) for name in report["malformed_documents"][:5])
        more = len(report["malformed_documents"]) - 5
        suffix = f" (+{more} more)" if more > 0 else ""
        print(f"  {len(report['malformed_documents'])} malformed skill document(s): {names}{suffix}")
    if report.get("undecodable_documents"):
        names = ", ".join(_display(name) for name in report["undecodable_documents"][:5])
        more = len(report["undecodable_documents"]) - 5
        suffix = f" (+{more} more)" if more > 0 else ""
        print(
            f"  {len(report['undecodable_documents'])} skill document(s) not valid UTF-8: "
            f"{names}{suffix} - re-save as UTF-8"
        )
    for issue in report.get("degraded", []):
        if issue.get("section") == "scope-scan":
            print(f"  scope scan unavailable: {_display(issue['reason'])}")

def _print_explain(report: dict) -> None:
    """Human-readable effective-resolution report (read-only)."""
    print(
        f"effective resolution for consumer {colors.COLORS.green(report['label'])} "
        f"({report['consumer']}) in {report['project'] or '-'}"
    )
    print(f"  policy: {report['policy']}  resolution: {report['resolution']}")
    print(f"  source: {report['source']}")
    for name, entry in sorted(report["skills"].items()):
        winner = entry.get("winner")
        if winner:
            print(
                f"  {name}: {entry['resolution']} -> {winner['tier']} "
                f"({winner['path']})"
            )
        else:
            print(f"  {name}: {entry['resolution']} - {entry['reason']}")
        for shadowed in entry.get("shadowed", []):
            print(f"      shadowed by {entry['winner_tier']}: {shadowed['path']}")
        for loaded in entry.get("also_loads", []):
            print(
                f"      also loads ({entry.get('also_loads_reason')}): "
                f"{loaded['path']}"
            )
    for note in report.get("notes", []):
        print(f"  note: {note}")
    for warning in report.get("warnings", []):
        print(f"  {colors.COLORS.yellow('warning:')} {warning}")


def _cmd_doctor_explain(args, consumer: str) -> int:
    """``doctor --explain CONSUMER [--project DIR] [--skill NAME]`` (issue #12)."""
    project = getattr(args, "project", None) or None
    if project is None and consumer.strip().lower() in effective.CONSUMERS:
        project = "."
    report = effective.explain(
        consumer, project, skill=getattr(args, "skill", None) or None
    )
    if getattr(args, "json", False):
        _print_json(report)
    elif report["resolution"] in ("unknown-consumer", "missing-project"):
        print(f"error: {report['reason']}", file=sys.stderr)
        if report.get("known_consumers"):
            print(
                "known consumers: " + ", ".join(report["known_consumers"]),
                file=sys.stderr,
            )
    else:
        _print_explain(report)
    if report["resolution"] in ("unknown-consumer", "missing-project"):
        return EXIT_ERROR
    return EXIT_OK


def cmd_stats(args, store: Store) -> int:
    scope = getattr(args, "scope", None)
    if scope and scope not in ("global", None, ""):
        if scope == "all":
            summary = scopes.list_scopes()
            if args.json:
                _print_json({"scopes": summary, "all_total": sum(s["count"] for s in summary)})
                return EXIT_OK
            print(colors.COLORS.bold("scopes:"))
            for s in summary:
                print(f"  {s['label']} ({s['id']}): {s['count']} skills")
            print(f"{colors.COLORS.bold('all total:')} {sum(s['count'] for s in summary)}")
            return EXIT_OK
        rows = scopes.scan_scope(scope)
        if args.json:
            _print_json({"scope": scope, "count": len(rows), "skills": rows})
            return EXIT_OK
        print(f"{colors.COLORS.bold(scope + ':')} {len(rows)} skills")
        return EXIT_OK
    stats = store.stats()
    if args.json:
        _print_json(stats)
        return EXIT_OK
    labels = [
        ("total", stats["total"]),
        ("active", stats["active"]),
        ("disabled", stats["disabled"]),
        ("trashed", stats["trashed"]),
        ("size on disk", stats["size_bytes"]),
        ("database size", stats["db_bytes"]),
    ]
    for label, value in labels:
        print(f"{colors.COLORS.bold(label + ':')} {value}")
    if stats["categories"]:
        print(colors.COLORS.bold("categories:"))
        for category, count in stats["categories"].items():
            print(f"  {_display(str(category or '(none)'))}: {count}")
    return EXIT_OK


def cmd_trash_list(args, store: Store) -> int:
    rows = store.trash_list()
    if getattr(args, "json", False):
        _print_json(rows)
        return EXIT_OK
    if not rows:
        print("trash is empty")
        return EXIT_OK
    header = ["NAME", "SIZE", "TRASHED"]
    table = [
        [row["name"], str(row["size_bytes"]), row["modified"] or "-"]
        for row in rows
    ]
    print(_render_table([header] + table))
    return EXIT_OK


def cmd_trash_purge(args, store: Store) -> int:
    result = store.purge_trash()
    if args.json:
        _print_json(result)
    else:
        print(f"purged {len(result['purged'])} trashed skills")
    return EXIT_OK


def cmd_templates_list(args, store: Store) -> int:
    names = templates_mod.list_templates(store.templates_dir)
    if getattr(args, "json", False):
        _print_json(names)
        return EXIT_OK
    if not names:
        print("no templates; create one with 'skills-mgr templates new NAME'")
        return EXIT_OK
    for name in names:
        print(name)
    return EXIT_OK


def cmd_templates_new(args, store: Store) -> int:
    try:
        path = templates_mod.create_template(store.templates_dir, args.name, args.body)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    except FileExistsError as exc:
        raise StoreError(str(exc)) from exc
    if args.json:
        _print_json({"name": args.name, "path": str(path)})
    else:
        print(f"created template {colors.COLORS.green(args.name)} at {path}")
    return EXIT_OK


def cmd_history(args, store: Store) -> int:
    if args.limit < 1 or args.limit > 200:
        raise StoreError("--limit must be between 1 and 200")
    rows = store.history(name=args.name, limit=args.limit)
    snapshots = []
    if args.name:
        snapshots = list_snapshots(store.data_dir, "global", args.name)
    if args.json:
        _print_json({"history": rows, "snapshots": snapshots} if args.name else rows)
        return EXIT_OK
    if not rows:
        print("no history recorded")
    else:
        header = ["WHEN", "ACTION", "NAME"]
        table = [
            [row["at"] or "-", row["action"], row["name"] or "-"] for row in rows
        ]
        print(_render_table([header] + table))
    if args.name:
        print(f"snapshots for {args.name}: {', '.join(snapshots) if snapshots else '(none)'}")
    return EXIT_OK


def cmd_db_rebuild(args, store: Store) -> int:
    result = store.db_rebuild()
    if getattr(args, "json", False):
        _print_json(result)
    else:
        print(
            f"rebuilt database: {result['added']} added, "
            f"{result['updated']} updated, {result['removed']} removed"
        )
    return EXIT_OK


def cmd_db_resync(args, store: Store) -> int:
    result = store.resync()
    if args.json:
        _print_json(result)
    else:
        print(f"resync complete: {result['added']} added, {result['removed']} removed")
    return EXIT_OK


def cmd_sync(args, store: Store) -> int:
    result = scopes.sync_skill(args.name, args.from_scope, args.to_scopes, force=args.force)
    if args.json:
        _print_json(result)
        return EXIT_OK
    synced = ", ".join(result.get("synced") or []) or "(none)"
    skipped = result.get("skipped") or []
    print(f"synced {result['name']} from {result['from_scope']} to: {synced}")
    if skipped:
        for entry in skipped:
            print(f"  skipped {entry.get('scope')}: {entry.get('reason')}")
    return EXIT_OK


def cmd_scopes(args, store: Store) -> int:
    summary = scopes.list_scopes()
    if args.json:
        _print_json(_scope_json_rows(summary, getattr(args, "no_tokens", False)))
        return EXIT_OK
    if not summary:
        print("no scopes found")
        return EXIT_OK
    show_tokens = not getattr(args, "no_tokens", False)
    if show_tokens:
        header = ["ID", "LABEL", "COUNT", "TOKENS", "PATH"]
        table = [[s["id"], s["label"], str(s["count"]), str(s.get("tokens", 0)), s["path"]] for s in summary]
    else:
        header = ["ID", "LABEL", "COUNT", "PATH"]
        table = [[s["id"], s["label"], str(s["count"]), s["path"]] for s in summary]
    print(_render_table([header] + table))
    return EXIT_OK


def _scope_json_rows(rows: list[dict], no_tokens: bool) -> list[dict]:
    if not no_tokens:
        return rows
    return [{key: value for key, value in row.items()
             if key not in {"tokens", "avg_tokens", "max_tokens"}} for row in rows]


def _token_input_text(text: str) -> str:
    if not text.startswith("@"):
        return text
    try:
        return Path(text[1:]).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeError, RuntimeError, ValueError):
        raise StoreError("cannot read --text file as UTF-8; check the path and encoding") from None


def cmd_tokens(args, store: Store) -> int:
    window = window_name(getattr(args, "window", None))
    scope = scope_from_args(args)
    if args.text:
        raw = _token_input_text(args.text)
        est = estimate(raw, window=window)
        if args.json:
            _print_json(est)
            return EXIT_OK
        print(f"tokens: {est['tokens']} ({est['method']})  window {window} {est['window_tokens']}  {est['pct_window']}%")
        return EXIT_OK
    if args.name:
        rec = scopes.find_skill(args.name, scope)
        est = estimate(scopes.record_text(rec), window=window)
        est["name"] = args.name
        est["scope"] = rec.get("scope", scope)
        if args.json:
            _print_json(est)
            return EXIT_OK
        print(f"{args.name} [{est['scope']}]  tokens: {est['tokens']} ({est['method']})  {est['pct_window']}% of {window} ({est['window_tokens']})")
        body_tokens = estimate(rec.get("body") or "", window=window)["tokens"]
        print(f"  chars: {est['chars']}  lines: {est['lines']}  frontmatter ~{max(0, est['tokens'] - body_tokens)} tok  body ~{body_tokens} tok")
        return EXIT_OK
    agg = aggregate(scopes.list_all() if scope in ("all", None, "") else scopes.scan_scope(scope), window)
    wtok, pct = agg["window_tokens"], agg["pct_window"]
    if args.json:
        _print_json(agg)
        return EXIT_OK
    print(f"scope: {scope}  window: {window} ({wtok})  total {agg['total_tokens']} tok ({format_tokens(agg['total_tokens'])})  {pct}%")
    print(f"  count: {agg['count']}  avg: {agg['avg_tokens']}  max: {agg['max_tokens']}")
    if agg.get("largest"):
        print("  largest:")
        for e in agg["largest"]:
            print(f"    {e['name']} [{e.get('scope','')}]  {e['tokens']} tok")
    return EXIT_OK


def _install_preview_output(args, source, runner, scope, agents, skills_filter,
                            copied, list_flag) -> int:
    """Print the offline registry bridge preview (no network, no execution)."""
    plan = install.registry_bridge_plan(
        source,
        runner=runner,
        scope=scope,
        agents=agents,
        skills=skills_filter,
        copy=copied,
        list_only=list_flag,
        trust_confirmed=bool(getattr(args, "trust_confirmed", False)),
        content_hash=getattr(args, "registry_hash", None),
    )
    if args.json:
        _print_json(plan)
        return EXIT_OK
    print("registry preview (offline — no registry request, no execution)")
    print(f"  spec          {plan['spec']}")
    if plan["registry_id"]:
        print(f"  registry id   {plan['registry_id']}")
    if plan["page_url"]:
        print(f"  page          {plan['page_url']}")
    for index, link in enumerate(plan["audit_links"]):
        label = "audit" if index == 0 else ""
        print(f"  {label:<13} {link['url']}")
    print(f"  target scope  {plan['target_scope']}")
    print(f"  install       {plan['install_command']}")
    print(f"  hash          {plan['content_hash'] or 'not provided (registry reads need a Vercel OIDC token; deferred)'}")
    print(f"  trust         {'confirmed' if plan['trust_confirmed'] else 'not confirmed'}")
    for index, blocker in enumerate(plan["blockers"]):
        label = "blocker" if index == 0 else ""
        print(f"  {label:<13} {blocker}")
    print(f"  policy        {plan['policy']}")
    return EXIT_OK


def _registry_operation(args, store: Store) -> int:
    """Run an explicit registry read or review/commit through install."""
    client = install.registry_client(store)
    allow_stale = bool(getattr(args, "allow_stale", False))
    if getattr(args, "browse", False):
        result = client.browse(
            page=args.page, per_page=args.per_page, view=args.view,
            allow_stale=allow_stale,
        )
        title = "registry leaderboard"
    elif getattr(args, "search", None) is not None:
        result = client.search(args.search, allow_stale=allow_stale)
        title = "registry search"
    elif getattr(args, "curated", False):
        result = client.curated(allow_stale=allow_stale)
        title = "registry curated"
    else:
        result = install.registry_fetch(
            store,
            source=args.source,
            review_id=getattr(args, "review", None) or None,
            trust_confirmed=bool(getattr(args, "trust_confirmed", False)),
            scope=scope_from_args(args),
            expected_hash=getattr(args, "registry_hash", None),
            allow_stale=allow_stale,
            external_scan=_external_scan_flag(args),
        )
        title = "registry fetch"
    if args.json:
        _print_json(result)
        return EXIT_OK
    if getattr(args, "fetch", False):
        if result.get("review_id"):
            print(f"review required for {result['registry']['id']}")
            print(f"  review id     {result['review_id']}")
            print(f"  snapshot hash {result['registry']['snapshot_hash']}")
            print("  mutation      none (commit only after a separate review)")
            _external_scan_text(result.get("inspection", {}).get("external_scan"), indent="  ")
        else:
            print(f"installed {result['name']} from {result['registry']['id']}")
            print(f"  path          {result['path']}")
            print(f"  snapshot hash {result['registry']['snapshot_hash']}")
            print(f"  cache         {result['registry']['cache_state']}")
        return EXIT_OK
    print(title)
    rows = result.get("data", [])
    if title == "registry curated":
        for owner in rows:
            if isinstance(owner, dict):
                print(f"  {owner.get('owner', '-')}: {owner.get('totalSkills', 0)} skills")
        print(f"  cache         {result['_registry']['cache_state']}")
        return EXIT_OK
    for entry in rows:
        if isinstance(entry, dict):
            print(
                f"  {entry.get('id', entry.get('name', '-'))}"
                f"  {entry.get('installs', 0)} installs"
                f"  {entry.get('url', '')}"
            )
    print(f"  cache         {result['_registry']['cache_state']}")
    return EXIT_OK


def cmd_install(args, store: Store) -> int:
    if (
        getattr(args, "browse", False)
        or getattr(args, "search", None) is not None
        or getattr(args, "curated", False)
        or getattr(args, "fetch", False)
    ):
        return _registry_operation(args, store)
    runner = install.install_runner(getattr(args, "runner", None))
    agents = getattr(args, "agent", None)
    skills_filter = getattr(args, "skill", None)
    scope = getattr(args, "scope", None) or "global"
    source = install.install_source(getattr(args, "source", ""))
    copied = bool(getattr(args, "copy", False))
    list_flag = bool(getattr(args, "list_only", False))
    cmd = install.install_argv(source, runner, scope, agents, skills_filter, copied, list_flag)
    cmd_str = " ".join(cmd)
    if getattr(args, "preview", False):
        return _install_preview_output(args, source, runner, scope, agents, skills_filter, copied, list_flag)
    if getattr(args, "dry_run", False):
        if args.json:
            _print_json({"command": cmd_str, "runner": runner, "source": args.source, "executed": False})
        else:
            print(cmd_str)
        return EXIT_OK
    if not args.json:
        print(f"running: {cmd_str}")
    result = install.run_install(cmd)
    if args.json:
        _print_json({"command": cmd_str, **result,
                     "stdout": result["stdout"][-4000:], "stderr": result["stderr"][-4000:]})
    else:
        if result["stdout"]:
            print(result["stdout"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr)
    return EXIT_OK if result["exit_code"] == 0 else EXIT_ERROR


def cmd_gui(args, store: Store) -> int:
    try:
        from . import webapp
    except (ImportError, ValueError, RuntimeError) as exc:
        _err(str(exc))
        return EXIT_ERROR
    return webapp.run(
        store,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
    )


def _update_preview_text(result: dict) -> None:
    """Render safe, ordered human-readable evidence for one update review."""
    target = result.get("target") or {}
    source = result.get("source") or {}
    print(f"target: {_display(str(target.get('name', '-')))}")
    print(f"scope: {_display(str(target.get('scope', '-')))}")
    print(f"path: {_display(str(target.get('physical_path', '-')))}")
    print(f"source: {_display(str(source.get('kind', '-')))} {_display(str(source.get('value', '-')))}")
    print(f"review: {_display(str(result.get('review_state', '-')))}")
    if result.get("review_expires_at"):
        print(f"expires: {_display(str(result['review_expires_at']))}")
    print(f"current hash: {_display(str(result.get('current_hash', '-')))}")
    print(f"candidate hash: {_display(str(result.get('candidate_hash', '-')))}")
    comparison = result.get("comparison") or {}
    for key in ("added", "removed", "changed", "line_ending_only"):
        values = comparison.get(key) or []
        print(f"{key.replace('_', ' ')}: {', '.join(_display(str(value)) for value in values) or '-'}")
    validation = result.get("validation") or {}
    print(f"validation: {'valid' if validation.get('valid') else 'blocked'}")
    for item in (validation.get("errors") or []) + (validation.get("warnings") or []):
        print(f"  {_display(str(item.get('level', 'notice')))}: {_display(str(item.get('message', item)))}")
    risk = result.get("risk") or {}
    print(f"risk: {_display(str(risk.get('policy', 'advisory-only')))}")
    for finding in risk.get("findings") or []:
        print(f"  {_display(str(finding))}")
    _external_scan_text(result.get("external_scan"))
    print(f"activation preserved: {'yes' if result.get('activation_preserved') else 'no'}")
    print(f"snapshot required: {'yes' if result.get('snapshot_required_before_commit') else 'no'}")
    print(f"commit allowed: {'yes' if result.get('commit_allowed') else 'no'}")
    if result.get("review_id"):
        print(f"apply with: skills-mgr update apply {_display(str(target.get('name', 'NAME')))} {result['review_id']} --scope {_display(str(target.get('scope', 'global')))} --yes")


def _external_scan_flag(args) -> dict | None:
    """Map --external-scan / --external-scan-llm onto scan options."""
    if getattr(args, "external_scan_llm", False):
        return scan_options("llm")
    return scan_options(bool(getattr(args, "external_scan", False)))


def _external_scan_text(evidence: dict | None, indent: str = "") -> None:
    """Print sanitized external-scanner evidence; untrusted text goes through _display."""
    if not evidence:
        return
    status = _display(str(evidence.get("status", "-")))
    print(f"{indent}external scan: {_display(str(evidence.get('tool', '-')))} {status} ({_display(str(evidence.get('mode', '-')))})")
    print(f"{indent}  policy: {_display(str(evidence.get('policy', '-')))}")
    if evidence.get("reason"):
        print(f"{indent}  reason: {_display(str(evidence['reason']))}")
    reported = evidence.get("reported") or {}
    if reported:
        print(f"{indent}  reported by tool: score {_display(str(reported.get('score', '-')))}, {_display(str(reported.get('recommendation', '-')))}")
    for finding in evidence.get("findings") or []:
        where = f"{finding.get('file') or '-'}:{finding.get('line') or '-'}"
        print(f"{indent}  {_display(str(finding.get('severity', '-')))} {_display(str(finding.get('id', '-')))} {_display(where)} {_display(str(finding.get('finding') or finding.get('pattern') or ''))}")
    if evidence.get("omitted"):
        print(f"{indent}  ... {evidence['omitted']} more findings omitted")
    for note in evidence.get("egress") or []:
        print(f"{indent}  egress: {_display(str(note))}")


def cmd_update(args, store: Store) -> int:
    """Run the approved local source-update review/apply/snapshot surface."""
    scope = scope_from_args(args)
    if scope == "all":
        raise StoreError("update mutations cannot use --scope all; choose one exact scope")
    operation = getattr(args, "update_command", None)
    if operation == "preview":
        if args.source_dir:
            result = source_update.prepare_local_update(
                store.data_dir, args.name, scope, args.source_dir, target_path=args.target_path,
                external_scan=_external_scan_flag(args),
            )
        else:
            result = source_update.prepare_snapshot_update(
                store.data_dir, args.name, scope, args.snapshot_id, target_path=args.target_path,
                external_scan=_external_scan_flag(args),
            )
        if args.json:
            _print_json(result)
        else:
            _update_preview_text(result)
        return EXIT_ERROR if result.get("review_state") in {"blocked", "source-unavailable", "target-unavailable"} else EXIT_OK
    if operation == "apply":
        result = source_update.commit_update_review(
            store.data_dir,
            args.review_id,
            name=args.name,
            scope=scope,
            target_path=args.target_path,
            approve=True,
        )
        if args.json:
            _print_json(result)
        else:
            print(f"applied reviewed update to {_display(args.name)}")
            print(f"snapshot: {_display(str(result.get('snapshot_id', '-')))}")
            if result.get("warning"):
                print(f"warning: {_display(str(result['warning']))}")
        return EXIT_OK
    if operation == "snapshots":
        result = source_update.list_update_snapshots(
            store.data_dir, args.name, scope, target_path=args.target_path
        )
        if args.json:
            _print_json(result)
        else:
            if not result:
                print("no source-update snapshots")
            for snapshot in result:
                print(f"{_display(str(snapshot.get('snapshot_id', '-')))}  {_display(str(snapshot.get('created_at', '-')))}  {_display(str(snapshot.get('activation_state', '-')))}")
        return EXIT_OK
    raise StoreError("update requires preview, apply, or snapshots")


COMMANDS = {
    "cmd_ai": cmd_ai,
    "cmd_init": cmd_init,
    "cmd_list": cmd_list,
    "cmd_create": cmd_create,
    "cmd_add": cmd_add,
    "cmd_view": cmd_view,
    "cmd_edit": cmd_edit,
    "cmd_open": cmd_open,
    "cmd_remove": cmd_remove,
    "cmd_disable": cmd_disable,
    "cmd_enable": cmd_enable,
    "cmd_validate": cmd_validate,
    "cmd_search": cmd_search,
    "cmd_import": cmd_import,
    "cmd_export": cmd_export,
    "cmd_backup": cmd_backup,
    "cmd_restore": cmd_restore,
    "cmd_doctor": cmd_doctor,
    "cmd_stats": cmd_stats,
    "cmd_trash_list": cmd_trash_list,
    "cmd_trash_purge": cmd_trash_purge,
    "cmd_templates_list": cmd_templates_list,
    "cmd_templates_new": cmd_templates_new,
    "cmd_history": cmd_history,
    "cmd_db_rebuild": cmd_db_rebuild,
    "cmd_db_resync": cmd_db_resync,
    "cmd_sync": cmd_sync,
    "cmd_scopes": cmd_scopes,
    "cmd_tokens": cmd_tokens,
    "cmd_install": cmd_install,
    "cmd_gui": cmd_gui,
    "cmd_update": cmd_update,
}

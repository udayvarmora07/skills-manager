"""Private CLI command handlers.

The parser lives in :mod:`skillsmgr.cli_parser`; output helpers live in
:mod:`skillsmgr.cli_output`. This module owns the per-command behavior behind
the ``cmd_*`` names the parser wires. ``skillsmgr.cli`` re-exports these names
as compatibility adapters so existing callers keep working.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess  # nosec B404 - reviewed editor and allowlisted installer calls use list argv.
import sys
import tempfile
from pathlib import Path

from . import colors
from . import search as search_mod
from . import templates as templates_mod
from .diagnostics import diagnose as _diagnose
from .cli_output import (
    err as _output_err,
    print_json as _output_print_json,
    render_table as _output_render_table,
    sanitize_text as _output_sanitize_text,
    truncate as _output_truncate,
)
from .store import Store, StoreError
from .validator import validate_skill, validate_skill_name

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPT = 130

# Character class shared with the REST /api/install route for ecosystem
# source/agent/skill values that are forwarded into runner commands.
_SAFE_SOURCE_RE = re.compile(r"[A-Za-z0-9_@./:+-]+")
_MAX_INSTALL_VALUE = 256


_print_json = _output_print_json
_err = _output_err
_truncate = _output_truncate
_render_table = _output_render_table
#: CLI-3: untrusted skill fields (description, category, notes) come from
#: imported archives and from directories other tools wrote.  They are printed
#: through this seam so an ESC payload can never spoof or re-align output.
_display = _output_sanitize_text


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
    root = Path(record["path"])
    for candidate in ("SKILL.md", "SKILL.md.disabled"):
        candidate_path = root / candidate
        if candidate_path.is_file():
            return candidate_path
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


def make_store(args) -> Store:
    """Build a Store for parsed CLI args, honoring ``--data-dir``/color flags."""
    if args.data_dir:
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(args.data_dir).expanduser())
    if args.color == "always":
        colors.COLORS.enabled = True
    elif args.color == "never":
        colors.COLORS.enabled = False
    store = Store()
    # Ensure the index schema exists so every command (not just `init` and
    # read paths that self-initialize) works on a fresh data directory;
    # `init_db` is idempotent and runs after name validation.
    store.init_db()
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
        from .scopes import list_all as _list_all

        rows = _list_all()
    elif scope != "global":
        from .scopes import scan_scope as _scan_scope

        rows = _scan_scope(scope)
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
        from .scopes import get_raw as _get_raw, get_skill as _get_skill

        if args.raw:
            print(_get_raw(scope, args.name), end="")
            return EXIT_OK
        record = _get_skill(scope, args.name)
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
        from . import paths as _paths

        for name in sorted(p.name for p in _paths.skills_dir().iterdir() if p.is_dir()):
            try:
                root = _paths.safe_skill_path(_paths.skills_dir(), name)
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
    if isinstance(document, list):
        return {"iteration": 1, "runs": document}
    if not isinstance(document, dict):
        raise StoreError("eval runs file must contain an object or a list")
    iteration = document.get("iteration", 1)
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
        raise StoreError("eval runs iteration must be a positive integer")
    return {"iteration": iteration, "runs": document.get("runs")}


def _eval_workspace(name: str, root: Path, store: Store, args) -> Path:
    """Resolve the eval workspace: explicit override, store default, or beside."""
    from . import evals as evals_mod

    override = getattr(args, "workspace", None)
    if override:
        workspace = Path(override).expanduser()
        if evals_mod._workspace_is_managed(workspace, store.data_dir):
            raise StoreError("eval workspace must not be inside the managed skills tree")
        return workspace
    if getattr(args, "path", None):
        workspace = evals_mod.workspace_for_dir(root, store.data_dir, name)
    else:
        workspace = evals_mod.workspace_for(store.data_dir, name)
    if evals_mod._workspace_is_managed(workspace, store.data_dir):
        raise StoreError("eval workspace must not be inside the managed skills tree")
    return workspace


def _eval_report(name: str, root: Path, store: Store, args, runs_document) -> dict:
    """Build the advisory eval report for one validated skill directory."""
    from . import evals as evals_mod

    report = evals_mod.load_cases(root)
    report["workspace"] = str(_eval_workspace(name, root, store, args))
    report["workspace_override"] = bool(getattr(args, "workspace", None))
    if runs_document is None:
        return report
    blocking = [issue for issue in report["issues"] if issue["level"] == "error"]
    if blocking:
        raise StoreError(
            f"cannot record eval runs for '{name}': {blocking[0]['message']}"
        )
    if not report["cases"]:
        raise StoreError(f"cannot record eval runs for '{name}': no eval cases found")
    workspace = Path(report["workspace"])
    report["recording"] = evals_mod.record_runs(
        workspace, runs_document["iteration"], report["cases"],
        runs_document["runs"],
    )
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


def search_full_record(match: dict, scope: str, store: Store, get_skill) -> dict:
    """Rehydrate one search match through the public detail seam."""
    match_scope = match.get("scope", scope)
    if match_scope == "global":
        return store.get(match["name"])
    return get_skill(match_scope, match["name"])


def cmd_search(args, store: Store) -> int:
    if args.limit is not None and args.limit < 1:
        raise StoreError("--limit must be a positive integer")
    scope = scope_from_args(args)
    from .scopes import get_skill as _get_skill, search_all as _search_all

    matches = _search_all(args.term, scope_id=scope, store=store)
    # search_all returns the historical scope-facing rows. Rehydrate each
    # match through the public detail seam so the CLI scorer sees bodies, but
    # retain the original match row for output compatibility.
    pool = []
    output_by_id = {}
    for match in matches:
        full = search_full_record(match, scope, store, _get_skill)
        full.update({key: value for key, value in match.items() if key != "body"})
        pool.append(full)
        output_by_id[id(full)] = search_output_row(match, scope)
    ranked_full = search_mod.rank_results(pool, args.term) if pool else []
    ranked = [(output_by_id[id(record)], score) for record, score in ranked_full]
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
        from .scopes import restore_snapshot as _restore_snapshot

        result = _restore_snapshot(scope, args.name, snapshot)
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


def _doctor_scope_report(scope_id: str) -> dict:
    """Audit one non-global scope directly from its filesystem tree.

    Agent scopes have no Store/index to compare, so the shared loader scan is
    the source of truth.  In particular, malformed documents must remain
    visible to this command instead of being hidden behind ``store.doctor()``.
    """
    from . import scopes
    from .loader import scan_dir

    scope = next(item for item in scopes.known_scopes() if item.id == scope_id)
    entries = scan_dir(scope.base, recursive=scope.recursive, include_husks=True)
    malformed = sorted(
        str(entry["name"])
        for entry in entries
        if entry.get("malformed")
    )
    undecodable = sorted(
        str(entry["name"])
        for entry in entries
        if entry.get("decode_error")
    )
    conflicting = sorted(
        str(entry["name"])
        for entry in entries
        if entry.get("document_conflict")
    )
    return {
        "scope": scope_id,
        "path": str(scope.base),
        "skills_on_disk": len(entries),
        "malformed_documents": malformed,
        "undecodable_documents": undecodable,
        "conflicting_documents": conflicting,
        "ok": not malformed,
    }


def _global_hygiene_records(store: Store) -> list[dict]:
    """Scan the global tree directly so unindexed husks remain evidence."""
    from .loader import scan_dir

    rows = scan_dir(store.skills_dir, include_husks=True)
    physical_root = str(store.skills_dir.resolve())
    for row in rows:
        row["scope"] = "global"
        row["scope_label"] = "Global"
        row["consumer"] = "skills-manager"
        row["physical_root"] = physical_root
        row["path"] = row.get("path") or str(store.skills_dir / row["name"])
        try:
            row["physical_path"] = str(Path(row["path"]).resolve())
        except OSError:
            row["physical_path"] = str(row["path"])
    return rows


def _hygiene_records(store: Store, scope: str) -> tuple[list[dict], list[dict]]:
    """Acquire bounded-scope observations without widening filesystem roots."""
    from . import scopes

    if scope == "global":
        return _global_hygiene_records(store), []
    if scope != "all":
        return scopes.scan_scope(scope), []
    records = []
    degraded = []
    for descriptor in scopes.known_scopes():
        if descriptor.id != "global" and not descriptor.base.is_dir():
            continue
        try:
            records.extend(
                _global_hygiene_records(store)
                if descriptor.id == "global"
                else scopes.scan_scope(descriptor.id)
            )
        except Exception as exc:
            degraded.append({
                "section": "scope-scan",
                "scope": descriptor.id,
                "reason": _truncate(str(exc), 512),
            })
    return records, degraded


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


def cmd_doctor(args, store: Store) -> int:
    scope = scope_from_args(args)
    from . import scopes

    known = {item.id: item for item in scopes.known_scopes()}
    if scope != "all" and scope not in known:
        raise StoreError(f"unknown scope {scope!r}")
    explain_consumer = getattr(args, "explain", None)
    if explain_consumer:
        return _cmd_doctor_explain(args, explain_consumer)
    hygiene = bool(getattr(args, "hygiene", False))
    report = (
        store.doctor()
        if scope == "global"
        else _doctor_scope_report(scope)
        if scope != "all"
        else store.doctor()
    )
    if hygiene:
        from .hygiene import hygiene_report

        records, degraded = _hygiene_records(store, scope)
        report["hygiene"] = hygiene_report(records, scope=scope)
        report["hygiene"]["degraded"].extend(degraded)
        report["hygiene"]["degraded"] = sorted(
            report["hygiene"]["degraded"],
            key=lambda item: (str(item.get("section", "")), str(item.get("scope", "")), str(item.get("reason", ""))),
        )
    if args.json:
        if scope == "all":
            try:
                from .scopes import find_duplicates as _dupes_json

                report["duplicates"] = _dupes_json()
            except Exception as exc:
                _diagnose("doctor scope=all duplicate enrichment failed", exc)
                report["duplicates"] = []
                report.setdefault("degraded", []).append(
                    {
                        "section": "scope/duplicates",
                        "reason": "duplicate enrichment was unavailable",
                    }
                )
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
    if report.get("malformed_documents"):
        names = ", ".join(report["malformed_documents"][:5])
        more = len(report["malformed_documents"]) - 5
        suffix = f" (+{more} more)" if more > 0 else ""
        print(f"  {len(report['malformed_documents'])} malformed skill document(s): {names}{suffix}")
    if report.get("undecodable_documents"):
        names = ", ".join(report["undecodable_documents"][:5])
        more = len(report["undecodable_documents"]) - 5
        suffix = f" (+{more} more)" if more > 0 else ""
        print(
            f"  {len(report['undecodable_documents'])} skill document(s) not valid UTF-8: "
            f"{names}{suffix} - re-save as UTF-8"
        )
    if report.get("db_integrity") and report["db_integrity"] != "ok":
        print(f"  database integrity check failed: {report['db_integrity']}")
    # Also show scope summary when --scope all.
    if scope == "all":
        try:
            from .scopes import find_duplicates as _dupes
            from .scopes import list_scopes as _list_scopes

            for s in _list_scopes():
                print(f"  {s['label']} ({s['id']}): {s['count']} skills at {s['path']}")
            dupes = _dupes()
            if dupes:
                print(f"  {len(dupes)} skill name(s) present in multiple scopes:")
                for d in dupes:
                    flag = " (descriptions differ)" if d["descriptions_differ"] else ""
                    print(f"    {d['name']}: {', '.join(d['scopes'])}{flag}")
        except Exception as exc:
            _diagnose("doctor scope=all enrichment failed", exc)
            print("  scope and duplicate summary unavailable; inspect diagnostics", file=sys.stderr)
    if hygiene:
        _render_hygiene_text(report["hygiene"])
        return EXIT_OK
    return EXIT_OK if report.get("ok") else EXIT_ERROR


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
    from . import effective

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
            from .scopes import list_scopes as _list_scopes

            scopes = _list_scopes()
            if args.json:
                _print_json({"scopes": scopes, "all_total": sum(s["count"] for s in scopes)})
                return EXIT_OK
            print(colors.COLORS.bold("scopes:"))
            for s in scopes:
                print(f"  {s['label']} ({s['id']}): {s['count']} skills")
            print(f"{colors.COLORS.bold('all total:')} {sum(s['count'] for s in scopes)}")
            return EXIT_OK
        from .scopes import scan_scope as _scan_scope

        rows = _scan_scope(scope)
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
        from .store import list_snapshots as _list_snapshots

        snapshots = _list_snapshots(store.data_dir, "global", args.name)
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
    from .scopes import sync_skill as _sync_skill

    result = _sync_skill(args.name, args.from_scope, args.to_scopes, force=args.force)
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
    from .scopes import list_scopes as _list_scopes

    scopes = _list_scopes()
    if args.json:
        _print_json(scopes)
        return EXIT_OK
    if not scopes:
        print("no scopes found")
        return EXIT_OK
    show_tokens = not getattr(args, "no_tokens", False)
    if show_tokens:
        header = ["ID", "LABEL", "COUNT", "TOKENS", "PATH"]
        table = [[s["id"], s["label"], str(s["count"]), str(s.get("tokens", 0)), s["path"]] for s in scopes]
    else:
        header = ["ID", "LABEL", "COUNT", "PATH"]
        table = [[s["id"], s["label"], str(s["count"]), s["path"]] for s in scopes]
    print(_render_table([header] + table))
    return EXIT_OK


def cmd_tokens(args, store: Store) -> int:
    from .tokens import WINDOWS as _WINDOWS, estimate as _est, format_tokens as _fmt

    window = getattr(args, "window", None) or "claude"
    if window not in _WINDOWS:
        raise StoreError(f"unknown window {window!r}; choose from {', '.join(_WINDOWS)}")
    scope = scope_from_args(args)
    if args.text:
        raw = args.text
        if raw.startswith("@"):
            p = Path(raw[1:]).expanduser()
            raw = p.read_text(encoding="utf-8") if p.is_file() else raw
        est = _est(raw, window=window)
        if args.json:
            _print_json(est)
            return EXIT_OK
        print(f"tokens: {est['tokens']} ({est['method']})  window {window} {est['window_tokens']}  {est['pct_window']}%")
        return EXIT_OK
    if args.name:
        from .scopes import get_skill as _get_skill, list_all as _list_all

        if scope not in ("all", "global"):
            rec = _get_skill(scope, args.name)
        else:
            rec = next((r for r in _list_all() if r["name"] == args.name), None)
            if rec is None:
                raise StoreError(f"skill '{args.name}' not found")
            rec = _get_skill(rec.get("scope", "global"), args.name)
        p = Path(rec.get("path", "")) if rec.get("path") else None
        raw = ""
        if p and p.is_dir():
            for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                if cand.is_file():
                    raw = cand.read_text(encoding="utf-8")
                    break
        if not raw:
            raw = rec.get("body", "") or ""
        est = _est(raw, window=window)
        est["name"] = args.name
        est["scope"] = rec.get("scope", scope)
        if args.json:
            _print_json(est)
            return EXIT_OK
        print(f"{args.name} [{est['scope']}]  tokens: {est['tokens']} ({est['method']})  {est['pct_window']}% of {window} ({est['window_tokens']})")
        print(f"  chars: {est['chars']}  lines: {est['lines']}  frontmatter ~{max(0, est['tokens'] - _est(rec.get('body','') or '', window=window)['tokens'])} tok  body ~{_est(rec.get('body','') or '', window=window)['tokens']} tok")
        return EXIT_OK
    # Aggregate
    if scope in ("all", None, ""):
        from .scopes import list_all as _list_all
        from .tokens import aggregate as _agg

        agg = _agg(_list_all())
    else:
        from .scopes import scan_scope as _scan_scope
        from .tokens import aggregate as _agg2

        agg = _agg2(_scan_scope(scope))
    wtok = _WINDOWS[window]
    pct = round(agg["total_tokens"] / wtok * 100, 1) if wtok else 0
    if args.json:
        agg["window"] = window
        agg["window_tokens"] = wtok
        agg["pct_window"] = pct
        _print_json(agg)
        return EXIT_OK
    print(f"scope: {scope}  window: {window} ({wtok})  total {agg['total_tokens']} tok ({_fmt(agg['total_tokens'])})  {pct}%")
    print(f"  count: {agg['count']}  avg: {agg['avg_tokens']}  max: {agg['max_tokens']}")
    if agg.get("largest"):
        print("  largest:")
        for e in agg["largest"]:
            print(f"    {e['name']} [{e.get('scope','')}]  {e['tokens']} tok")
    return EXIT_OK


def install_command_for_display(source: str, runner: str, scope: str, agents, skills_filter, copy_mode: bool, list_only: bool) -> str:
    """Render the ecosystem runner command shown in ``--dry-run`` output."""
    from .insights import install_command_line

    return install_command_line(source, runner, scope, agents, skills_filter, copy_mode, list_only)


def _install_preview_output(args, source, runner, scope, agents, skills_filter,
                            copied, list_flag) -> int:
    """Print the offline registry bridge preview (no network, no execution)."""
    from .insights import registry_bridge_plan

    plan = registry_bridge_plan(
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


def validated_install_runner(runner: str | None) -> str:
    """Resolve the ecosystem runner, rejecting values outside the CLI contract."""
    runner = (runner or "npx").strip() or "npx"
    if runner == "uvx":
        raise StoreError("uvx does not apply to the npm 'skills' package; use npx/pnpm dlx/yarn dlx/bunx. For Python packages use pipx/uvx with a PyPI package.")
    allowed = {"npx", "pnpm", "yarn", "bunx", "bun"}
    if runner not in allowed:
        raise StoreError(f"unsupported runner {runner!r}")
    return runner


def validated_install_value(label: str, value: str) -> str:
    """Accept one ecosystem value, rejecting command-injection shapes.

    Mirrors the REST /api/install route: only the shared character class is
    accepted and leading dashes are rejected either way.
    """
    value = str(value).strip()
    invalid_path = (
        not value
        or len(value) > _MAX_INSTALL_VALUE
        or not _SAFE_SOURCE_RE.fullmatch(value)
        or value.startswith("-")
        or value.startswith(("/", "\\"))
        or "/../" in f"/{value}/"
        or value in {".", ".."}
        or any(segment in {".", ".."} for segment in value.replace("\\", "/").split("/"))
        or (len(value) >= 2 and value[1] == ":")
    )
    if invalid_path:
        if label == "source":
            raise StoreError("invalid source value")
        raise StoreError(f"invalid {label} value {value!r}")
    return value


def validated_install_source(raw: str | None) -> str:
    """Require a non-empty ecosystem source and validate it."""
    source = (raw or "").strip()
    if not source:
        raise StoreError("source is required (e.g. vercel-labs/agent-skills)")
    return validated_install_value("source", source)


def _registry_client(store: Store):
    from .registry import RegistryClient

    return RegistryClient(store.data_dir)


def _registry_operation(args, store: Store) -> int:
    """Run an explicit registry read or review/commit through install."""
    client = _registry_client(store)
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
        if scope_from_args(args) != "global":
            raise StoreError("install --fetch currently targets the global manager store only")
        review_id = getattr(args, "review", None)
        if review_id:
            if not getattr(args, "trust_confirmed", False):
                raise StoreError("registry commit requires --trust-confirmed after reviewing the fetched snapshot")
            result = _commit_registry_review(store, review_id)
        else:
            if getattr(args, "trust_confirmed", False):
                raise StoreError("fetch and trust confirmation are separate: fetch first, then commit with --review REVIEW_ID --trust-confirmed")
            result = _prepare_registry_skill(
                store,
                validated_install_source(args.source),
                expected_hash=getattr(args, "registry_hash", None),
                allow_stale=allow_stale,
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


def _prepare_registry_skill(store: Store, spec: str, *, expected_hash: str | None,
                            allow_stale: bool) -> dict:
    """Fetch and inspect a registry snapshot without touching the managed Store."""
    from .frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
    from .insights import risk_scan
    from .registry import (
        materialize_snapshot,
        provenance_for_snapshot,
        write_registry_review,
    )

    snapshot = _registry_client(store).fetch(
        spec, expected_hash=expected_hash, allow_stale=allow_stale
    )
    name = snapshot.get("slug")
    try:
        name = validate_skill_name(name)
    except (TypeError, ValueError) as exc:
        raise StoreError(f"registry slug cannot be installed as a skill name: {name!r}") from exc
    local_snapshot = snapshot
    normalization = None
    try:
        frontmatter, body = parse_frontmatter(
            next(entry["contents"] for entry in snapshot["files"] if entry["path"] == "SKILL.md")
        )
        remote_name = frontmatter.get("name")
        if isinstance(remote_name, str) and remote_name != name:
            local_files = [dict(entry) for entry in snapshot["files"]]
            root_file = next(entry for entry in local_files if entry["path"] == "SKILL.md")
            frontmatter["name"] = name
            root_file["contents"] = dump_frontmatter(
                frontmatter, key_order=list(frontmatter.keys())
            ) + body
            local_snapshot = dict(snapshot)
            local_snapshot["files"] = local_files
            local_snapshot.pop("hash", None)
            normalization = f"frontmatter.name {remote_name!r} normalized to slug {name!r}"
            local_snapshot["normalization"] = normalization
    except (FrontmatterError, StopIteration):
        pass
    provenance = provenance_for_snapshot(local_snapshot)
    if normalization is not None:
        provenance["remote_hash"] = snapshot.get("hash")
        provenance["hash_verified"] = bool(snapshot.get("hash_verified"))
    with tempfile.TemporaryDirectory(prefix="skillsmgr-registry-review-") as temporary:
        staged = Path(temporary) / name
        materialize_snapshot(local_snapshot, staged)
        validation = validate_skill(name, staged)
        if validation.errors:
            summary = "; ".join(issue.message for issue in validation.errors[:3])
            raise StoreError(f"registry snapshot failed validation before install: {summary}")
        risk_findings = risk_scan({
            "name": name,
            "body": validation.body,
            "allowed_tools": validation.data.get("allowed-tools"),
        })
    inspection = {
        "validation": {
            "valid": validation.valid,
            "warnings": [
                {"level": issue.level, "key": issue.key, "message": issue.message}
                for issue in validation.warnings
            ],
        },
        "risk": {
            "policy": "advisory-only; heuristic evidence is not a safety or trust verdict",
            "findings": risk_findings,
        },
        "reviewed_before_install": False,
        "review_required": True,
        "target_scope": "global",
    }
    local_snapshot["remote_hash"] = snapshot.get("hash")
    review = write_registry_review(store.data_dir, local_snapshot, inspection)
    registry = dict(review["registry"])
    registry["remote_hash"] = snapshot.get("hash")
    registry["remote_registry_hash"] = snapshot["registry_hash"]
    registry["registry_hash"] = provenance["registry_hash"]
    registry["snapshot_hash"] = provenance["local_snapshot_hash"]
    registry["normalization"] = normalization
    return {
        "review_id": review["review_id"],
        "review_expires_at": review["expires_at"],
        "registry": registry,
        "inspection": inspection,
    }


def _commit_registry_review(store: Store, review_id: str) -> dict:
    """Commit one registry review under the cross-process single-use lock."""
    from .atomic_io import mutation_lock
    from .registry import _review_path

    with mutation_lock(_review_path(store.data_dir, review_id)):
        return _commit_registry_review_unlocked(store, review_id)


def _commit_registry_review_unlocked(store: Store, review_id: str) -> dict:
    """Commit one reviewed registry snapshot without another network request."""
    from .frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
    from .insights import risk_scan
    from .registry import (
        materialize_snapshot,
        mark_registry_review_committed,
        provenance_for_snapshot,
        read_registry_review,
        write_provenance,
    )

    review = read_registry_review(store.data_dir, review_id)
    snapshot = review["snapshot"]
    name = snapshot.get("slug")
    try:
        name = validate_skill_name(name)
    except (TypeError, ValueError) as exc:
        raise StoreError(f"registry slug cannot be installed as a skill name: {name!r}") from exc
    provenance = provenance_for_snapshot(snapshot)
    remote_hash = snapshot.get("remote_hash")
    if remote_hash is not None:
        provenance["remote_hash"] = remote_hash
        provenance["hash_verified"] = bool(snapshot.get("hash_verified"))
    with tempfile.TemporaryDirectory(prefix="skillsmgr-registry-commit-") as temporary:
        staged = Path(temporary) / name
        materialize_snapshot(snapshot, staged)
        validation = validate_skill(name, staged)
        if validation.errors:
            summary = "; ".join(issue.message for issue in validation.errors[:3])
            raise StoreError(f"registry review failed validation before install: {summary}")
        risk_findings = risk_scan({
            "name": name,
            "body": validation.body,
            "allowed_tools": validation.data.get("allowed-tools"),
        })
        write_provenance(staged, provenance)
        installed = store.add(staged, name=name)
    committed = mark_registry_review_committed(store.data_dir, review_id)
    registry = dict(committed["registry"])
    registry["remote_hash"] = remote_hash
    registry["normalization"] = snapshot.get("normalization")
    inspection = dict(review["inspection"])
    inspection.update({
        "risk": {
            "policy": "advisory-only; heuristic evidence is not a safety or trust verdict",
            "findings": risk_findings,
        },
        "reviewed_before_install": True,
        "review_required": False,
        "review_id": review_id,
        "target_scope": "global",
    })
    return {
        "name": installed["name"],
        "path": installed["path"],
        "registry": registry,
        "inspection": inspection,
    }


def _fetch_registry_skill(store: Store, spec: str, *, expected_hash: str | None,
                          allow_stale: bool) -> dict:
    """Compatibility adapter for callers that used the old private helper."""
    return _prepare_registry_skill(
        store, spec, expected_hash=expected_hash, allow_stale=allow_stale
    )


def cmd_install(args, store: Store) -> int:
    if (
        getattr(args, "browse", False)
        or getattr(args, "search", None) is not None
        or getattr(args, "curated", False)
        or getattr(args, "fetch", False)
    ):
        return _registry_operation(args, store)
    runner = validated_install_runner(getattr(args, "runner", None))
    agents = getattr(args, "agent", None)
    skills_filter = getattr(args, "skill", None)
    scope = getattr(args, "scope", None) or "global"
    source = validated_install_source(getattr(args, "source", ""))
    copied = bool(getattr(args, "copy", False))
    list_flag = bool(getattr(args, "list_only", False))
    for label, values in (("agent", agents), ("skill", skills_filter)):
        for value in values or []:
            validated_install_value(label, value)
    cmd_str = install_command_for_display(source, runner, scope, agents, skills_filter, copied, list_flag)
    if getattr(args, "preview", False):
        return _install_preview_output(args, source, runner, scope, agents, skills_filter, copied, list_flag)
    if getattr(args, "dry_run", False):
        if args.json:
            _print_json({"command": cmd_str, "runner": runner, "source": args.source, "executed": False})
        else:
            print(cmd_str)
        return EXIT_OK
    # Build subprocess command through the same shared renderer, so the printed
    # dry-run text and the executed argv can never drift apart.  List-only is an
    # executing mode: the runner's ``-l`` output is the requested inventory.
    from .insights import install_argv

    cmd = install_argv(source, runner, scope, agents, skills_filter, copied, list_flag)
    if not args.json:
        print(f"running: {cmd_str}")

    try:
        proc = subprocess.run(  # nosec B603 - runner and argv are validated before execution; shell stays false.
            cmd, capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError as exc:
        raise StoreError(f"runner not found: {exc}")
    except subprocess.TimeoutExpired as exc:
        raise StoreError(f"timed out after 120s: {exc}")
    if args.json:
        _print_json({"command": cmd_str, "exit_code": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
    else:
        if proc.stdout:
            print(proc.stdout[-8000:])
        if proc.stderr:
            print(proc.stderr[-8000:], file=sys.stderr)
    return EXIT_OK if proc.returncode == 0 else EXIT_ERROR


def cmd_gui(args, store: Store) -> int:
    try:
        from . import webapp
    except (ImportError, ValueError, RuntimeError) as exc:
        _output_err(str(exc))
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
    print(f"activation preserved: {'yes' if result.get('activation_preserved') else 'no'}")
    print(f"snapshot required: {'yes' if result.get('snapshot_required_before_commit') else 'no'}")
    print(f"commit allowed: {'yes' if result.get('commit_allowed') else 'no'}")
    if result.get("review_id"):
        print(f"apply with: skills-mgr update apply {_display(str(target.get('name', 'NAME')))} {result['review_id']} --scope {_display(str(target.get('scope', 'global')))} --yes")


def cmd_update(args, store: Store) -> int:
    """Run the approved local source-update review/apply/snapshot surface."""
    from . import source_update

    scope = scope_from_args(args)
    if scope == "all":
        raise StoreError("update mutations cannot use --scope all; choose one exact scope")
    operation = getattr(args, "update_command", None)
    if operation == "preview":
        if args.source_dir:
            result = source_update.prepare_local_update(
                store.data_dir, args.name, scope, args.source_dir, target_path=args.target_path
            )
        else:
            result = source_update.prepare_snapshot_update(
                store.data_dir, args.name, scope, args.snapshot_id, target_path=args.target_path
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

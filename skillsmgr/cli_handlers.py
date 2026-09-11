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
import subprocess
import sys
from pathlib import Path

from . import colors
from . import search as search_mod
from . import templates as templates_mod
from .cli_output import err as _output_err, print_json as _output_print_json, render_table as _output_render_table, truncate as _output_truncate
from .store import Store, StoreError
from .validator import validate_skill, validate_skill_name

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPT = 130

# Character class shared with the REST /api/install route for ecosystem
# source/agent/skill values that are forwarded into runner commands.
_SAFE_SOURCE_RE = re.compile(r"[A-Za-z0-9_@./:+-]+")


_print_json = _output_print_json
_err = _output_err
_truncate = _output_truncate
_render_table = _output_render_table


def parse_metadata(pairs: list[str] | None) -> dict | None:
    """Parse repeated ``KEY=VALUE`` CLI metadata flags."""
    if not pairs:
        return None
    data = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"metadata must be KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        data[key.strip()] = value
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
    elif command == "validate" and not getattr(args, "path", None):
        names.extend(getattr(args, "names", []) or [])
    elif command == "trash" and getattr(args, "trash_command", None) == "restore":
        names.append(getattr(args, "name", ""))

    for raw_name in names:
        try:
            validate_skill_name(str(raw_name).strip())
        except ValueError as exc:
            raise StoreError(str(exc)) from exc


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
            print(f"{colors.COLORS.bold(key + ':')} {value}")
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
        print(f"{colors.COLORS.bold(key + ':')} {value}")
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
    status = subprocess.call(shlex.split(editor) + [str(md_path)])
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
        return Path(override).expanduser()
    if getattr(args, "path", None):
        return evals_mod.workspace_for_dir(root, store.data_dir, name)
    return evals_mod.workspace_for(store.data_dir, name)


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


def cmd_doctor(args, store: Store) -> int:
    report = store.doctor()
    scope = getattr(args, "scope", None)
    if args.json:
        if scope == "all":
            try:
                from .scopes import find_duplicates as _dupes_json

                report["duplicates"] = _dupes_json()
            except Exception:
                pass
        _print_json(report)
        return EXIT_OK
    if report.get("ok"):
        print(f"{colors.COLORS.green('ok:')} filesystem and database are consistent")
    else:
        print(f"{colors.COLORS.yellow('issues found:')}")
    if report.get("orphan_dirs"):
        print(f"  {len(report['orphan_dirs'])} unindexed skill directories")
    if report.get("stale_rows"):
        print(f"  {len(report['stale_rows'])} database rows without files")
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
        except Exception:
            pass
    return EXIT_OK if report.get("ok") else EXIT_ERROR


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
            print(f"  {category or '(none)'}: {count}")
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
        print(f"purged {result['purged']} trashed skills")
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
    value = str(value)
    if not _SAFE_SOURCE_RE.fullmatch(value) or value.startswith("-"):
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


def cmd_install(args, store: Store) -> int:
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
    if getattr(args, "dry_run", False) or getattr(args, "list_only", False):
        if args.json:
            _print_json({"command": cmd_str, "runner": runner, "source": args.source, "executed": False})
        else:
            print(cmd_str)
        return EXIT_OK
    # Build subprocess command through the same shared renderer, so the printed
    # dry-run text and the executed argv can never drift apart.
    from .insights import install_argv

    cmd = install_argv(source, runner, scope, agents, skills_filter, copied, False)
    if not args.json:
        print(f"running: {cmd_str}")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
}

"""Command-line interface for skills-mgr.

Exit codes: 0 on success, 1 on operational errors, 2 on usage errors,
130 on interrupt.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import __version__, colors
from . import search as search_mod
from . import templates as templates_mod
from .colors import COLORS
from .store import Store, StoreError
from .validator import validate_skill, validate_skill_name

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPT = 130


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _err(message: str) -> None:
    print(f"{COLORS.red('error:')} {message}", file=sys.stderr)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _render_table(rows: list[list[str]]) -> str:
    widths = [0] * len(rows[0])
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = []
    for index, row in enumerate(rows):
        cells = []
        for i, cell in enumerate(row):
            if i < len(row) - 1:
                cells.append(cell.ljust(widths[i]))
            else:
                cells.append(cell)
        line = "   ".join(cells)
        if index == 0:
            line = COLORS.bold(line)
        lines.append(line)
    return "\n".join(lines)


def _parse_metadata(pairs: list[str] | None) -> dict | None:
    if not pairs:
        return None
    data = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"metadata must be KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        data[key.strip()] = value
    return data


def _read_body(args) -> str | None:
    if args.body is not None and args.body_file is not None:
        raise ValueError("use only one of --body or --body-file")
    if args.body_file is not None:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body


def _skill_md_path(store: Store, name: str) -> Path:
    record = store.get(name)
    if record["path"] is None:
        raise StoreError(f"skill '{name}' has no directory on disk")
    root = Path(record["path"])
    for candidate in ("SKILL.md", "SKILL.md.disabled"):
        candidate_path = root / candidate
        if candidate_path.is_file():
            return candidate_path
    raise StoreError(f"skill '{name}' has no SKILL.md (or SKILL.md.disabled)")


def _scope_from_args(args) -> str:
    return (getattr(args, "scope", None) or "global").strip() or "global"


def _validate_cli_names(args) -> None:
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


def _make_store(args) -> Store:
    if args.data_dir:
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(args.data_dir).expanduser())
    if args.color == "always":
        COLORS.enabled = True
    elif args.color == "never":
        COLORS.enabled = False
    return Store()


def _add_scope_arg(parser) -> None:
    parser.add_argument(
        "--scope",
        metavar="SCOPE",
        default="global",
        help="scope: global, all, or an agent id (claude-code, codex, cursor, opencode, gemini, agents). Default: global",
    )


def cmd_init(args, store: Store) -> int:
    store.init_db()
    if args.json:
        _print_json({"data_dir": str(store.data_dir), "ok": True})
    else:
        print(f"initialized {store.data_dir}")
    return EXIT_OK


def cmd_list(args, store: Store) -> int:
    scope = _scope_from_args(args)
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
            base = [row.get("scope", scope) ] + base
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
            metadata_extra=_parse_metadata(args.metadata),
            body=_read_body(args),
        )
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    if args.json:
        _print_json(result)
    else:
        print(f"created {COLORS.green(result['name'])} at {result['path']}")
    return EXIT_OK


def cmd_add(args, store: Store) -> int:
    result = store.add(args.path, name=args.name)
    if args.json:
        _print_json(result)
    else:
        print(f"installed {COLORS.green(result['name'])} from {args.path}")
    return EXIT_OK


def cmd_view(args, store: Store) -> int:
    scope = _scope_from_args(args)
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
            print(f"{COLORS.bold(key + ':')} {value}")
        return EXIT_OK
    record = store.get(args.name)
    if args.raw:
        print(_skill_md_path(store, args.name).read_text(encoding="utf-8"), end="")
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
        print(f"{COLORS.bold(key + ':')} {value}")
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
            metadata_extra=_parse_metadata(args.metadata),
            body=_read_body(args),
        )
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    if args.json:
        _print_json(result)
    elif result.get("changed"):
        print(f"updated {COLORS.green(args.name)}")
    else:
        print(f"no changes for {args.name}")
    return EXIT_OK


def cmd_open(args, store: Store) -> int:
    md_path = _skill_md_path(store, args.name)
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
        print(f"disabled {COLORS.yellow(args.name)}")
    return EXIT_OK


def cmd_enable(args, store: Store) -> int:
    store.enable(args.name)
    if args.json:
        _print_json({"name": args.name, "disabled": False})
    else:
        print(f"enabled {COLORS.green(args.name)}")
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
        results.append(
            {
                "name": name,
                "valid": result.valid,
                "errors": [issue.message for issue in result.errors],
                "warnings": [issue.message for issue in result.warnings],
            }
        )
        if not result.valid:
            any_errors = True
    if args.json:
        _print_json({"valid": not any_errors, "skills": results})
        return EXIT_OK if not any_errors else EXIT_ERROR
    for entry in results:
        status = COLORS.green("ok") if entry["valid"] else COLORS.red("invalid")
        print(f"{entry['name']}: {status}")
        for message in entry["warnings"]:
            print(f"  {COLORS.yellow('warn')}  {message}")
        for message in entry["errors"]:
            print(f"  {COLORS.red('error')} {message}")
    return EXIT_OK if not any_errors else EXIT_ERROR


def cmd_search(args, store: Store) -> int:
    if args.limit is not None and args.limit < 1:
        raise StoreError("--limit must be a positive integer")
    scope = _scope_from_args(args)
    if scope == "all":
        from .scopes import search_all as _search_all

        pool = _search_all(args.term, scope_id="all")
        # search_all already ranked; rebuild ranked tuples for display.
        ranked = search_mod.rank_results(pool, args.term) if pool else []
    elif scope != "global":
        from .scopes import search_all as _search_all

        pool = _search_all(args.term, scope_id=scope)
        ranked = search_mod.rank_results(pool, args.term) if pool else []
    else:
        ranked = search_mod.rank_results(store.list(), args.term)
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
    result = store.import_(args.archive, force=args.force)
    if args.json:
        _print_json(result)
    else:
        print(
            f"imported {result['imported']}, skipped {result['skipped']} "
            f"from {result['source']}"
        )
    return EXIT_OK


def cmd_export(args, store: Store) -> int:
    result = store.export(args.dest)
    if args.json:
        _print_json({"path": str(result)})
    else:
        print(f"exported skills to {result}")
    return EXIT_OK


def cmd_backup(args, store: Store) -> int:
    result = store.backup(args.dest)
    if args.json:
        _print_json({"path": str(result)})
    else:
        print(f"backup written to {result}")
    return EXIT_OK


def cmd_restore(args, store: Store) -> int:
    result = store.restore(args.name)
    if args.json:
        _print_json(result)
    else:
        print(
            f"restored {COLORS.green(result['name'])} "
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
        print(f"{COLORS.green('ok:')} filesystem and database are consistent")
    else:
        print(f"{COLORS.yellow('issues found:')}")
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
            print(COLORS.bold("scopes:"))
            for s in scopes:
                print(f"  {s['label']} ({s['id']}): {s['count']} skills")
            print(f"{COLORS.bold('all total:')} {sum(s['count'] for s in scopes)}")
            return EXIT_OK
        from .scopes import scan_scope as _scan_scope

        rows = _scan_scope(scope)
        if args.json:
            _print_json({"scope": scope, "count": len(rows), "skills": rows})
            return EXIT_OK
        print(f"{COLORS.bold(scope + ':')} {len(rows)} skills")
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
        print(f"{COLORS.bold(label + ':')} {value}")
    if stats["categories"]:
        print(COLORS.bold("categories:"))
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
        print(f"created template {COLORS.green(args.name)} at {path}")
    return EXIT_OK


def cmd_history(args, store: Store) -> int:
    if args.limit < 1 or args.limit > 200:
        raise StoreError("--limit must be between 1 and 200")
    rows = store.history(name=args.name, limit=args.limit)
    if args.json:
        _print_json(rows)
        return EXIT_OK
    if not rows:
        print("no history recorded")
        return EXIT_OK
    header = ["WHEN", "ACTION", "NAME"]
    table = [
        [row["at"] or "-", row["action"], row["name"] or "-"] for row in rows
    ]
    print(_render_table([header] + table))
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
    scope = _scope_from_args(args)
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


def _install_command_for_display(source: str, runner: str, scope: str, agents, skills_filter, copy_mode: bool, list_only: bool) -> str:
    parts: list[str] = []
    if runner == "npx":
        parts = ["npx", "skills", "add", source]
    elif runner == "pnpm":
        parts = ["pnpm", "dlx", "skills", "add", source]
    elif runner == "yarn":
        parts = ["yarn", "dlx", "skills", "add", source]
    elif runner in ("bunx", "bun"):
        parts = ["bunx", "skills", "add", source]
    else:
        parts = ["npx", "skills", "add", source]
    if scope == "global":
        parts.append("-g")
    if agents:
        for a in agents:
            parts.extend(["-a", str(a)])
    if skills_filter:
        for s in skills_filter:
            parts.extend(["-s", str(s)])
    if copy_mode:
        parts.append("--copy")
    if list_only:
        parts.append("-l")
    return " ".join(parts)


def cmd_install(args, store: Store) -> int:
    runner = (getattr(args, "runner", None) or "npx").strip() or "npx"
    if runner == "uvx":
        raise StoreError("uvx does not apply to the npm 'skills' package; use npx/pnpm dlx/yarn dlx/bunx. For Python packages use pipx/uvx with a PyPI package.")
    allowed = {"npx", "pnpm", "yarn", "bunx", "bun"}
    if runner not in allowed:
        raise StoreError(f"unsupported runner {runner!r}")
    agents = getattr(args, "agent", None)
    skills_filter = getattr(args, "skill", None)
    scope = getattr(args, "scope", None) or "global"
    cmd_str = _install_command_for_display(args.source, runner, scope, agents, skills_filter, bool(getattr(args, "copy", False)), bool(getattr(args, "list_only", False)))
    if getattr(args, "dry_run", False) or getattr(args, "list_only", False):
        if args.json:
            _print_json({"command": cmd_str, "runner": runner, "source": args.source, "executed": False})
        else:
            print(cmd_str)
        return EXIT_OK
    # Build subprocess command.
    if runner == "npx":
        cmd = ["npx", "skills", "add", args.source]
    elif runner == "pnpm":
        cmd = ["pnpm", "dlx", "skills", "add", args.source]
    elif runner == "yarn":
        cmd = ["yarn", "dlx", "skills", "add", args.source]
    else:
        cmd = ["bunx", "skills", "add", args.source]
    if scope == "global":
        cmd.append("-g")
    if agents:
        for a in agents:
            cmd.extend(["-a", str(a)])
    if skills_filter:
        for s in skills_filter:
            cmd.extend(["-s", str(s)])
    if getattr(args, "copy", False):
        cmd.append("--copy")
    if not args.json:
        print(f"running: {cmd_str}")
    import subprocess as _sp

    try:
        proc = _sp.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise StoreError(f"runner not found: {exc}")
    except _sp.TimeoutExpired as exc:
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
        _err(str(exc))
        return EXIT_ERROR
    return webapp.run(
        store,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skills-mgr",
        description="Manage agentic AI skills (SKILL.md) from the command line.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--data-dir",
        metavar="PATH",
        help="override the data directory (default: $SKILLS_MANAGER_DATA or ~/.local/share/skills-manager)",
    )
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument(
        "--color", dest="color", action="store_const", const="always"
    )
    color_group.add_argument(
        "--no-color", dest="color", action="store_const", const="never"
    )
    parser.set_defaults(color=None)

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("init", help="create the data directories and database")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("list", aliases=["ls"], help="list installed skills")
    p.add_argument("--json", action="store_true")
    p.add_argument("--disabled", action="store_true", help="only disabled skills")
    p.add_argument("--category", metavar="CAT", help="filter by category")
    _add_scope_arg(p)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("create", help="create a new skill")
    p.add_argument("name")
    p.add_argument("-d", "--description", help="one-line description")
    p.add_argument("--license", help="license identifier")
    p.add_argument("--category", help="category")
    p.add_argument("--compatibility", help="compatibility notes")
    p.add_argument("--version", help="skill version")
    p.add_argument("--allowed-tools", help="space-separated allowed tools")
    p.add_argument(
        "--metadata", action="append", metavar="KEY=VALUE", help="extra frontmatter"
    )
    p.add_argument("--body", help="skill body text")
    p.add_argument("--body-file", metavar="PATH", help="read body from a file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("add", help="install an existing skill directory")
    p.add_argument("path")
    p.add_argument("--name", help="override the directory name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("view", help="show skill metadata (--raw shows SKILL.md)")
    p.add_argument("name")
    p.add_argument("--raw", action="store_true")
    p.add_argument("--json", action="store_true")
    _add_scope_arg(p)
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("edit", help="update skill metadata or body")
    p.add_argument("name")
    p.add_argument("-d", "--description")
    p.add_argument("--license")
    p.add_argument("--category")
    p.add_argument("--compatibility")
    p.add_argument("--version")
    p.add_argument("--allowed-tools")
    p.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    p.add_argument("--body")
    p.add_argument("--body-file", metavar="PATH")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("open", help="edit SKILL.md in $EDITOR")
    p.add_argument("name")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("remove", aliases=["rm"], help="trash or purge a skill")
    p.add_argument("name")
    action_group = p.add_mutually_exclusive_group()
    action_group.add_argument("--purge", action="store_true", help="delete permanently")
    action_group.add_argument("--trash", dest="purge", action="store_false")
    p.set_defaults(purge=False)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("disable", help="disable a skill")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_disable)

    p = sub.add_parser("enable", help="re-enable a disabled skill")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_enable)

    p = sub.add_parser("validate", help="lint skills against the schema")
    p.add_argument("names", nargs="*", metavar="NAME")
    p.add_argument("--all", action="store_true", help="validate every installed skill")
    p.add_argument("--path", metavar="DIR", help="validate a skill directory")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("search", help="search skills by name or description")
    p.add_argument("term")
    p.add_argument("--limit", type=int, metavar="N", help="max results")
    p.add_argument("--json", action="store_true")
    _add_scope_arg(p)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("import", help="install skills from an archive")
    p.add_argument("archive")
    p.add_argument("--force", action="store_true", help="overwrite existing skills")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("export", help="package skills into a tar.gz archive")
    p.add_argument("--dest", metavar="PATH")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("backup", help="alias for export")
    p.add_argument("--dest", metavar="PATH")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("restore", help="restore a skill from the trash")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("doctor", help="check filesystem/database consistency")
    p.add_argument("--json", action="store_true")
    _add_scope_arg(p)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("stats", help="show store statistics")
    p.add_argument("--json", action="store_true")
    _add_scope_arg(p)
    p.set_defaults(func=cmd_stats)

    trash = sub.add_parser("trash", help="manage the trash")
    trash_sub = trash.add_subparsers(dest="trash_command", metavar="ACTION")
    p = trash_sub.add_parser("list", help="list trashed skills")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_trash_list)
    p = trash_sub.add_parser("restore", help="restore a trashed skill")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_restore)
    p = trash_sub.add_parser("purge", help="permanently delete all trashed skills")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_trash_purge)
    trash.set_defaults(func=cmd_trash_list)

    templates = sub.add_parser("templates", help="manage skill templates")
    templates_sub = templates.add_subparsers(dest="templates_command", metavar="ACTION")
    p = templates_sub.add_parser("list", help="list templates")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_templates_list)
    p = templates_sub.add_parser("new", help="create a template")
    p.add_argument("name")
    p.add_argument("--body")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_templates_new)
    templates.set_defaults(func=cmd_templates_list)

    p = sub.add_parser("history", help="show the action log")
    p.add_argument("name", nargs="?", help="filter to one skill")
    p.add_argument("--limit", type=int, default=50, metavar="N")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_history)

    db = sub.add_parser("db", help="database maintenance")
    db_sub = db.add_subparsers(dest="db_command", metavar="ACTION")
    p = db_sub.add_parser("rebuild", help="rebuild the index from disk")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_db_rebuild)
    p = db_sub.add_parser("resync", help="sync index entries with disk")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_db_resync)
    db.set_defaults(func=cmd_db_rebuild)

    p = sub.add_parser("sync", help="copy a skill from one scope to others (global -> all agents by default)")
    p.add_argument("name", help="skill name to sync")
    p.add_argument("--from", dest="from_scope", metavar="SCOPE", default="global", help="source scope (default: global)")
    p.add_argument("--to", dest="to_scopes", metavar="SCOPE", action="append", help="target scope(s); repeatable (default: all writable agents)")
    p.add_argument("--force", action="store_true", help="overwrite existing skills in targets")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("scopes", help="list known skill scopes and their counts")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-tokens", action="store_true", help="skip token totals (faster for large installs)")
    p.set_defaults(func=cmd_scopes)

    p = sub.add_parser("tokens", help="estimate token/context usage for a skill, text, or scope")
    p.add_argument("name", nargs="?", help="skill name; omit to aggregate over --scope")
    p.add_argument("--scope", metavar="SCOPE", default="all", help="scope for lookup/aggregate (global, claude-code, all, ...). Default: all")
    p.add_argument("--text", metavar="TEXT", help="raw text to estimate instead of a skill (prefix @ for file path)")
    p.add_argument("--window", metavar="WINDOW", default="claude", help="context window: claude (1M), claude-haiku (200k), gpt-5.6 (1.05M), gpt-5 (400k), gpt-4o (128k legacy), gemini (1M), gemini-2m (2M)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_tokens)

    p = sub.add_parser("install", help="install skills via npx/pnpm/yarn/bunx (wraps 'skills add'); uvx does not apply to this npm package")
    p.add_argument("source", help="source e.g. vercel-labs/agent-skills or owner/repo@skill")
    p.add_argument("--runner", metavar="RUNNER", default="npx", help="runner: npx (default), pnpm, yarn, bunx")
    p.add_argument("--scope", metavar="SCOPE", default="global", help="global (-g) vs project scope")
    p.add_argument("--agent", metavar="AGENT", action="append", help="target agent(s) e.g. claude-code; repeatable")
    p.add_argument("--skill", metavar="SKILL", action="append", help="filter to specific skill name(s); repeatable")
    p.add_argument("--copy", action="store_true", help="copy files instead of symlinking")
    p.add_argument("--list-only", action="store_true", help="list available skills without installing (-l)")
    p.add_argument("--dry-run", action="store_true", help="print command without executing")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser(
        "webui",
        aliases=["gui"],
        help="launch the local web UI (opens in your browser)",
    )
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="port (default: 8765)")
    p.add_argument("--no-browser", action="store_true", help="do not open the browser")
    p.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        _validate_cli_names(args)
        store = _make_store(args)
        return args.func(args, store) or EXIT_OK
    except (StoreError, ValueError, OSError) as exc:
        _err(str(exc))
        return EXIT_ERROR
    except KeyboardInterrupt:
        _err("interrupted")
        return EXIT_INTERRUPT
    except Exception as exc:
        _err(f"unexpected error: {exc}")
        return EXIT_ERROR

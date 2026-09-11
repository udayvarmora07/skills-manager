"""Private CLI parser construction.

``skillsmgr.cli`` keeps the canonical :func:`build_parser` entry point for
backwards compatibility; the per-command wiring lives here so the parser can
be reviewed without reading every command handler.
"""

from __future__ import annotations

import argparse

from . import __version__


def add_scope_arg(parser) -> None:
    """Attach the shared ``--scope`` flag to a command parser."""
    parser.add_argument(
        "--scope",
        metavar="SCOPE",
        default="global",
        help="scope: global, all, or an agent id (claude-code, codex, cursor, opencode, gemini, agents). Default: global",
    )


def build_parser(commands) -> argparse.ArgumentParser:
    """Build the ``skills-mgr`` parser, wiring ``commands`` handlers.

    ``commands`` maps command/registration helper names to callables so the
    handler module stays the single owner of command behavior. Only the
    registration names used below are required.
    """
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
    p.set_defaults(func=commands["cmd_init"])

    p = sub.add_parser("list", aliases=["ls"], help="list installed skills")
    p.add_argument("--json", action="store_true")
    p.add_argument("--disabled", action="store_true", help="only disabled skills")
    p.add_argument("--category", metavar="CAT", help="filter by category")
    add_scope_arg(p)
    p.set_defaults(func=commands["cmd_list"])

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
    p.set_defaults(func=commands["cmd_create"])

    p = sub.add_parser("add", help="install an existing skill directory")
    p.add_argument("path")
    p.add_argument("--name", help="override the directory name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_add"])

    p = sub.add_parser("view", help="show skill metadata (--raw shows SKILL.md)")
    p.add_argument("name")
    p.add_argument("--raw", action="store_true")
    p.add_argument("--json", action="store_true")
    add_scope_arg(p)
    p.set_defaults(func=commands["cmd_view"])

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
    p.set_defaults(func=commands["cmd_edit"])

    p = sub.add_parser("open", help="edit SKILL.md in $EDITOR")
    p.add_argument("name")
    p.set_defaults(func=commands["cmd_open"])

    p = sub.add_parser("remove", aliases=["rm"], help="trash or purge a skill")
    p.add_argument("name")
    action_group = p.add_mutually_exclusive_group()
    action_group.add_argument("--purge", action="store_true", help="delete permanently")
    action_group.add_argument("--trash", dest="purge", action="store_false")
    p.set_defaults(purge=False)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_remove"])

    p = sub.add_parser("disable", help="disable a skill")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_disable"])

    p = sub.add_parser("enable", help="re-enable a disabled skill")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_enable"])

    p = sub.add_parser("validate", help="lint skills against the schema")
    p.add_argument("names", nargs="*", metavar="NAME")
    p.add_argument("--all", action="store_true", help="validate every installed skill")
    p.add_argument("--path", metavar="DIR", help="validate a skill directory")
    p.add_argument("--evals", action="store_true", help="also report the advisory eval harness status (evals/evals.json)")
    p.add_argument("--evals-run", metavar="FILE", help="score eval runs from FILE and record results in the iteration workspace (advisory)")
    p.add_argument("--workspace", metavar="DIR", help="override the eval run workspace directory")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_validate"])

    p = sub.add_parser("search", help="search skills by name or description")
    p.add_argument("term")
    p.add_argument("--limit", type=int, metavar="N", help="max results")
    p.add_argument("--json", action="store_true")
    add_scope_arg(p)
    p.set_defaults(func=commands["cmd_search"])

    p = sub.add_parser("import", help="install skills from an archive")
    p.add_argument("archive")
    p.add_argument("--force", action="store_true", help="overwrite existing skills")
    p.add_argument("--full", action="store_true", help="also restore trash and templates from a full export")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_import"])

    p = sub.add_parser("export", help="package skills into a tar.gz archive")
    p.add_argument("--dest", metavar="PATH")
    p.add_argument("--full", action="store_true", help="also include trash and templates for full migration")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_export"])

    p = sub.add_parser("backup", help="alias for export")
    p.add_argument("--dest", metavar="PATH")
    p.add_argument("--full", action="store_true", help="also include trash and templates for full migration")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_backup"])

    p = sub.add_parser("restore", help="restore a skill from the trash")
    p.add_argument("name")
    p.add_argument("--snapshot", metavar="TS", help="roll back to a snapshot id instead of the trash")
    add_scope_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_restore"])

    p = sub.add_parser("doctor", help="check filesystem/database consistency")
    p.add_argument("--json", action="store_true")
    p.add_argument("--explain", metavar="CONSUMER", help="read-only effective-resolution diagnostic: derive which instance of a skill a consumer would load for --project (derived at read time; writes nothing)")
    p.add_argument("--project", metavar="DIR", help="with --explain: the project directory the consumer resolves from (default: the current directory)")
    p.add_argument("--skill", metavar="NAME", help="with --explain: explain one skill name only")
    add_scope_arg(p)
    p.set_defaults(func=commands["cmd_doctor"])

    p = sub.add_parser("stats", help="show store statistics")
    p.add_argument("--json", action="store_true")
    add_scope_arg(p)
    p.set_defaults(func=commands["cmd_stats"])

    trash = sub.add_parser("trash", help="manage the trash")
    trash_sub = trash.add_subparsers(dest="trash_command", metavar="ACTION")
    p = trash_sub.add_parser("list", help="list trashed skills")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_trash_list"])
    p = trash_sub.add_parser("restore", help="restore a trashed skill")
    p.add_argument("name")
    p.add_argument("--snapshot", metavar="TS", help="roll back to a snapshot id instead of the trash")
    add_scope_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_restore"])
    p = trash_sub.add_parser("purge", help="permanently delete all trashed skills")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_trash_purge"])
    trash.set_defaults(func=commands["cmd_trash_list"])

    templates = sub.add_parser("templates", help="manage skill templates")
    templates_sub = templates.add_subparsers(dest="templates_command", metavar="ACTION")
    p = templates_sub.add_parser("list", help="list templates")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_templates_list"])
    p = templates_sub.add_parser("new", help="create a template")
    p.add_argument("name")
    p.add_argument("--body")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_templates_new"])
    templates.set_defaults(func=commands["cmd_templates_list"])

    p = sub.add_parser("history", help="show the action log")
    p.add_argument("name", nargs="?", help="filter to one skill")
    p.add_argument("--limit", type=int, default=50, metavar="N")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_history"])

    db = sub.add_parser("db", help="database maintenance")
    db_sub = db.add_subparsers(dest="db_command", metavar="ACTION")
    p = db_sub.add_parser("rebuild", help="rebuild the index from disk")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_db_rebuild"])
    p = db_sub.add_parser("resync", help="sync index entries with disk")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_db_resync"])
    db.set_defaults(func=commands["cmd_db_rebuild"])

    p = sub.add_parser("sync", help="copy a skill from one scope to others (global -> all agents by default)")
    p.add_argument("name", help="skill name to sync")
    p.add_argument("--from", dest="from_scope", metavar="SCOPE", default="global", help="source scope (default: global)")
    p.add_argument("--to", dest="to_scopes", metavar="SCOPE", action="append", help="target scope(s); repeatable (default: all writable agents)")
    p.add_argument("--force", action="store_true", help="overwrite existing skills in targets")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_sync"])

    p = sub.add_parser("scopes", help="list known skill scopes and their counts")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-tokens", action="store_true", help="skip token totals (faster for large installs)")
    p.set_defaults(func=commands["cmd_scopes"])

    p = sub.add_parser("tokens", help="estimate token/context usage for a skill, text, or scope")
    p.add_argument("name", nargs="?", help="skill name; omit to aggregate over --scope")
    p.add_argument("--scope", metavar="SCOPE", default="all", help="scope for lookup/aggregate (global, claude-code, all, ...). Default: all")
    p.add_argument("--text", metavar="TEXT", help="raw text to estimate instead of a skill (prefix @ for file path)")
    p.add_argument("--window", metavar="WINDOW", default="claude", help="context window: claude (1M), claude-haiku (200k), gpt-5.6 (1.05M), gpt-5 (400k), gpt-4o (128k legacy), gemini (1M), gemini-2m (2M)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_tokens"])

    p = sub.add_parser("install", help="install skills via npx/pnpm/yarn/bunx (wraps 'skills add'); uvx does not apply to this npm package")
    p.add_argument("source", help="source e.g. vercel-labs/agent-skills or owner/repo@skill")
    p.add_argument("--runner", metavar="RUNNER", default="npx", help="runner: npx (default), pnpm, yarn, bunx")
    p.add_argument("--scope", metavar="SCOPE", default="global", help="global (-g) vs project scope")
    p.add_argument("--agent", metavar="AGENT", action="append", help="target agent(s) e.g. claude-code; repeatable")
    p.add_argument("--skill", metavar="SKILL", action="append", help="filter to specific skill name(s); repeatable")
    p.add_argument("--copy", action="store_true", help="copy files instead of symlinking")
    p.add_argument("--list-only", action="store_true", help="list available skills without installing (-l)")
    p.add_argument("--dry-run", action="store_true", help="print command without executing")
    p.add_argument("--preview", action="store_true", help="offline registry bridge preview: audit links, registry hash, and the exact install command (no network, no execution)")
    p.add_argument("--trust-confirmed", action="store_true", help="with --preview: record that the source and audit links were reviewed")
    p.add_argument("--registry-hash", metavar="HEX", help="with --preview: registry content hash stored for change detection")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=commands["cmd_install"])

    p = sub.add_parser(
        "webui",
        aliases=["gui"],
        help="launch the local web UI (opens in your browser)",
    )
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="port (default: 8765)")
    p.add_argument("--no-browser", action="store_true", help="do not open the browser")
    p.set_defaults(func=commands["cmd_gui"])

    return parser

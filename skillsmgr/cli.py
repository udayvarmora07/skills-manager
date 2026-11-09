"""Command-line entry point for skills-mgr.

Exit codes: 0 on success, 1 on operational errors, 2 on usage errors,
130 on interrupt.  The parser lives in :mod:`skillsmgr.cli_parser` and the
command behavior in :mod:`skillsmgr.cli_handlers`.
"""

from __future__ import annotations

from .cli_handlers import (
    COMMANDS,
    cmd_init,
    cmd_list,
    cmd_create,
    cmd_add,
    cmd_view,
    cmd_edit,
    cmd_open,
    cmd_remove,
    cmd_disable,
    cmd_enable,
    cmd_validate,
    cmd_search,
    cmd_import,
    cmd_export,
    cmd_backup,
    cmd_restore,
    cmd_doctor,
    cmd_stats,
    cmd_trash_list,
    cmd_trash_purge,
    cmd_templates_list,
    cmd_templates_new,
    cmd_history,
    cmd_db_rebuild,
    cmd_db_resync,
    cmd_sync,
    cmd_scopes,
    cmd_tokens,
    cmd_install,
    cmd_update,
    cmd_gui,
    EXIT_ERROR,
    EXIT_INTERRUPT,
    EXIT_OK,
    EXIT_USAGE,
    make_store,
    validate_cli_combinations,
    validate_cli_names,
)
from .cli_output import err as _err
from .cli_parser import build_parser as _build_parser
from .errors import StoreError
from .context import bound_store

__all__ = [
    "EXIT_OK",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "EXIT_INTERRUPT",
    "COMMANDS",
    "build_parser",
    "main",
    "cmd_init",
    "cmd_list",
    "cmd_create",
    "cmd_add",
    "cmd_view",
    "cmd_edit",
    "cmd_open",
    "cmd_remove",
    "cmd_disable",
    "cmd_enable",
    "cmd_validate",
    "cmd_search",
    "cmd_import",
    "cmd_export",
    "cmd_backup",
    "cmd_restore",
    "cmd_doctor",
    "cmd_stats",
    "cmd_trash_list",
    "cmd_trash_purge",
    "cmd_templates_list",
    "cmd_templates_new",
    "cmd_history",
    "cmd_db_rebuild",
    "cmd_db_resync",
    "cmd_sync",
    "cmd_scopes",
    "cmd_tokens",
    "cmd_install",
    "cmd_update",
    "cmd_gui",
]


def build_parser():
    """Build the CLI parser wired to the command handlers."""
    return _build_parser(COMMANDS)


def _run(args) -> int:
    validate_cli_names(args)
    validate_cli_combinations(args)
    store = make_store(args)
    # ``global`` resolves through this invocation's Store, not a stale one.
    with bound_store(store):
        return args.func(args, store) or EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return _run(args)
    except (StoreError, ValueError, OSError) as exc:
        _err(str(exc))
        return EXIT_ERROR
    except KeyboardInterrupt:
        _err("interrupted")
        return EXIT_INTERRUPT
    except Exception as exc:
        _err(f"unexpected error: {exc}")
        return EXIT_ERROR

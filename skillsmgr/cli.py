"""Command-line interface for skills-mgr.

Exit codes: 0 on success, 1 on operational errors, 2 on usage errors,
130 on interrupt.

The parser construction lives in :mod:`skillsmgr.cli_parser`, the command
handlers in :mod:`skillsmgr.cli_handlers`, and output helpers in
:mod:`skillsmgr.cli_output`. This module keeps the historical public names as
compatibility adapters.
"""

from __future__ import annotations

from . import __version__, colors  # noqa: F401  (re-exported for compatibility)
from . import search as search_mod  # noqa: F401
from . import templates as templates_mod  # noqa: F401
from .cli_handlers import (
    COMMANDS,
    EXIT_ERROR,
    EXIT_INTERRUPT,
    EXIT_OK,
    EXIT_USAGE,
    _SAFE_SOURCE_RE,
    cmd_add,
    cmd_backup,
    cmd_create,
    cmd_db_rebuild,
    cmd_db_resync,
    cmd_disable,
    cmd_doctor,
    cmd_edit,
    cmd_enable,
    cmd_export,
    cmd_gui,
    cmd_history,
    cmd_import,
    cmd_init,
    cmd_install,
    cmd_list,
    cmd_open,
    cmd_remove,
    cmd_restore,
    cmd_scopes,
    cmd_search,
    cmd_stats,
    cmd_sync,
    cmd_templates_list,
    cmd_templates_new,
    cmd_tokens,
    cmd_trash_list,
    cmd_trash_purge,
    cmd_validate,
    cmd_view,
    install_command_for_display,
    make_store,
    parse_metadata,
    read_body,
    scope_from_args,
    search_full_record,
    search_output_row,
    skill_md_path,
    validated_install_runner,
    validated_install_source,
    validated_install_value,
    validate_cli_names,
)
from .cli_output import err as _output_err, print_json as _output_print_json, render_table as _output_render_table, truncate as _output_truncate
from .cli_parser import add_scope_arg, build_parser as _build_parser_impl
from .store import Store, StoreError  # noqa: F401

# Historical private aliases (kept so external tools/tests keep working).
_print_json = _output_print_json
_err = _output_err
_truncate = _output_truncate
_render_table = _output_render_table

_parse_metadata = parse_metadata
_read_body = read_body
_skill_md_path = skill_md_path
_scope_from_args = scope_from_args
_validate_cli_names = validate_cli_names
_make_store = make_store
_add_scope_arg = add_scope_arg
_search_output_row = search_output_row
_search_full_record = search_full_record
_install_command_for_display = install_command_for_display
_validated_install_runner = validated_install_runner
_validated_install_value = validated_install_value
_validated_install_source = validated_install_source


def build_parser():
    """Build the CLI parser from the handler/command modules."""
    return _build_parser_impl(COMMANDS)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        validate_cli_names(args)
        store = make_store(args)
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
    "cmd_gui",
]

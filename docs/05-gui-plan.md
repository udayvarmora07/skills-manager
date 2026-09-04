# GUI Plan — GTK4 Desktop App (SUPERSEDED)

**Version 0.2.0**

**AI manifest**: **[NOTE] SUPERSEDED on 2026-08-14.** The GTK4 GUI plan is dead. The GUI is now a **local web UI** — see @docs/08-web-ui.md for the architecture, REST API, and frontend map. This file is kept only as a historical record of the abandoned approach (toolkit fights, `set_data` unsupported, Popover API differences — receipts in @docs/06-progress-log.md). `skillsmgr/gui.py` was deleted; the `gui` CLI command is now an alias of `webui`.

*Historical content below (from v0.1.0).*

## Toolkit

**[SPEC]** Target: GTK4 (gi 4.14) via PyGObject 3.48.2 on Wayland (DISPLAY=:0, XDG_SESSION_TYPE=wayland). Fallback: GTK3 3.24 import path. Launch check is a locked milestone item (task.md M2 last item).

**[SPEC]** GUI constraints (locked, from AGENTS.md):
- Use only the `Store` public API (docs/04-store-api.md); no direct `Path`/`sqlite3` access.
- Surface `StoreError`/`SkillNotFound` as clean dialogs — never raw tracebacks.
- No new Store methods, CLI commands, or schema changes without approval.
- `python3 -m skillsmgr gui` must not regress the CLI (`--help` unchanged).

## Window / view mapping

| GUI view | Mirrors CLI | Store calls |
|---|---|---|
| Main window: skill list (name, status, category, description, updated) | `list` / `list --disabled` | `Store.list` |
| Detail view: frontmatter + body | `view` | `Store.get` |
| Create dialog | `create` | `Store.create` |
| Import dialog (file picker) | `import` | `Store.import_` |
| Edit dialog (metadata fields + body) | `edit` | `Store.edit` |
| Open in editor button | `open` | `$EDITOR` (external) |
| Validate dialog (results pane) | `validate` | validator functions |
| Search bar (live filter) | `search` | `Store.search` + local filter |
| Disable/enable buttons | `disable` / `enable` | `Store.disable` / `Store.enable` |
| Remove dialog (trash vs purge choice) | `remove` | `Store.remove(purge=...)` |
| Trash view (list/restore/purge) | `trash list` / `restore` / `trash purge` | `Store.trash_list`, `Store.restore`, `Store.purge_trash` |
| History dialog | `history` | `Store.history` |
| Stats dialog | `stats` | `Store.stats` |
| Doctor dialog | `doctor` | `Store.doctor` |
| Templates dialog (list/new) | `templates list` / `new` | templates helpers |
| Export/backup dialog (file picker) | `export` / `backup` | `Store.export` / `Store.backup` |
| Restore dialog (file picker) | `restore` | `Store.restore` |
| DB dialog (rebuild/resync) | `db rebuild` / `db resync` | `Store.db_rebuild` / `Store.db_resync` |

**[NOTE]** Search in the GUI uses `Store.search` scoring (100 exact … 0 none, see docs/02-modules.md) for the query term, then applies live list filtering client-side for responsiveness.

## Layout (GTK4)

- `Gtk.ApplicationWindow` + `Gtk.HeaderBar` (title, search entry, actions menu).
- `Gtk.Paned`: left `Gtk.ListView` (skill rows, status column), right detail `Gtk.ScrolledWindow` + `Gtk.TextView` for body.
- Dialogs: `Gtk.Dialog`/`Gtk.AlertDialog` for errors and confirmations (trash vs purge).
- File pickers: `Gtk.FileDialog` (GTK4) for import/export/backup/restore.

## Error handling

**[SPEC]** Wrap every Store call; on `StoreError`/`SkillNotFound` show an alert dialog with the message, log a line, and keep the window usable. No tracebacks in UI. `KeyboardInterrupt`/GTK main-loop exits cleanly.

## Milestone 3 iteration loop

1. Run `python3 smoke_store.py` (must pass; store.py untouched unless a real bug is found).
2. Run `python3 -m skillsmgr --help` — no CLI regression.
3. Launch `python3 -m skillsmgr gui`; exercise every row of the mapping table above.
4. Fix every error found; log each iteration (date, what, result) in @docs/06-progress-log.md.
5. Loop until zero errors/bugs remain.

## Open questions

- `[?]` None for planning. Any GUI-only discovery (e.g. GTK3 fallback needs) goes here or is resolved in 06-progress-log.md.
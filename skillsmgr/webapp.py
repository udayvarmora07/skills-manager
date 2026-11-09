"""Local web UI backend for skills-mgr (stdlib only).

Serves a single-page frontend (``webui/``) plus a JSON REST API over the
Store public API. Binds to 127.0.0.1 only — this is local desktop
software, never a public service.
"""

from __future__ import annotations

import ipaddress
import os
import re
import select
import socket
import shutil
import subprocess  # nosec B404 - only the allowlisted installer and trusted opener use it.
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import ai, ai_ask, ai_budget, ai_concise, ai_draft, ai_evals, ai_overlap, ai_port, ai_profiles, ai_review, ai_skills, batch, doctor, effective, evals, install, scopes
from .documents import document_text
from .context import set_active_store
from .store import Store, StoreError, SkillNotFound
from .loader import scan_dir
from .tokens import DEFAULT_WINDOW, aggregate, estimate, window_name
from .diagnostics import diagnose as _diagnose
from .launcher_security import trusted_executable
from .web_security import RequestError, validate_request
from .web_serialization import json_bytes, parse_json_object
from .adapters import workspaces_payload
from .catalog import delete_profile, enrich_rows, load_catalog, profile_preview, save_profile, update_tags
from .external_scan import scan_options
from .path_safety import contained_path
from .source_update import cancel_update_review, commit_update_review, list_update_snapshots, prepare_local_update, prepare_snapshot_update, read_update_review
from .templates import create_template, list_templates, read_template, template_path
from .validator import validate_skill
from .web_upload import MAX_UPLOAD_BYTES, parse_multipart, staged_single_skill, upload_folder

_WEBUI_DIR = Path(__file__).resolve().parent / "webui"
_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    # The vendored typeface (SEC: offline by design). Serving woff2 as
    # application/octet-stream happens to work for a same-origin @font-face
    # fetch, but it is wrong on the wire and any stricter consumer downstream
    # would refuse it.
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}

def _client_disconnected(connection) -> bool:
    """Probe without consuming request data or blocking the handler."""
    try:
        readable, _, _ = select.select([connection], [], [], 0)
        return bool(readable) and connection.recv(1, socket.MSG_PEEK) == b""
    except BlockingIOError:
        return False
    except OSError:
        return True


_SKILL_FIELDS = ("description", "license", "category", "compatibility", "version", "allowed_tools", "body")


def _install_preview_payload(store: Store, data: dict, source: str, cmd_str: str,
                             runner: str) -> dict:
    """Build the non-executing ``/api/install`` payload.

    Without ``preview`` this is the historical ``{command, runner, source,
    executed}`` shape.  With ``preview: true`` it adds the offline registry
    bridge plan (audit links, registry hash slot, blockers) and still performs
    no registry request and no execution.
    """
    payload = {"command": cmd_str, "runner": runner, "source": source, "executed": False}
    if not data.get("preview"):
        return payload
    description = data.get("description")
    payload["registry"] = install.registry_bridge_plan(
        source,
        runner=runner,
        scope=str(data.get("scope", "global") or "global"),
        agents=_option_list(data.get("agents")),
        skills=_option_list(data.get("skills")),
        copy=bool(data.get("copy")),
        list_only=bool(data.get("list_only")),
        trust_confirmed=bool(data.get("trust_confirmed")),
        description=description if isinstance(description, str) else None,
        content_hash=data.get("registry_hash") if isinstance(data.get("registry_hash"), str) else None,
    )
    # A registry skill id installs that skill from its source, so the previewed
    # command is the bridge plan's mapping rather than the bare source command.
    payload["command"] = payload["registry"]["install_command"]
    return payload


def _install_command(data: dict) -> tuple[str, str, list[str]]:
    """Validate HTTP option shapes before shared installer value guards."""
    source = install.install_source(data.get("source"))
    raw_scope = data.get("scope", "global")
    raw_runner = data.get("runner", "npx")
    if not isinstance(raw_scope, str):
        raise StoreError("scope must be a string")
    if not isinstance(raw_runner, str):
        raise StoreError("runner must be a string")
    scope = raw_scope.strip() or "global"
    runner = install.install_runner(raw_runner)
    cmd_parts = install.install_argv(
        source, runner, scope,
        _option_list(data.get("agents")), _option_list(data.get("skills")),
        bool(data.get("copy")), bool(data.get("list_only")),
    )
    return source, runner, cmd_parts


def _registry_operation_kind(data: dict) -> str | None:
    """Validate and identify a registry operation in an install payload."""
    for flag in ("browse", "curated", "fetch"):
        if flag in data and not isinstance(data[flag], bool):
            raise StoreError(f"{flag} must be a boolean")
    operations = [flag for flag in ("browse", "curated", "fetch") if data.get(flag)]
    if data.get("search") is not None:
        operations.append("search")
    if len(operations) > 1:
        raise StoreError("install accepts only one registry operation")
    return operations[0] if operations else None


def _option_list(value) -> list | None:
    """Coerce one repeated install option into a list, or drop it.

    A bare string is a one-element list (what the UI sends for one target);
    any other non-list shape is dropped rather than guessed at.
    """
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else None


def _registry_read_result(client, operation: str, data: dict, allow_stale: bool) -> dict:
    """Run a read-only registry operation from an install payload."""
    if operation == "browse":
        return client.browse(
            page=data.get("page", 0), per_page=data.get("per_page", 25),
            view=data.get("view", "all-time"), allow_stale=allow_stale,
        )
    if operation == "search":
        if not isinstance(data.get("search"), str):
            raise StoreError("search must be a string")
        return client.search(
            data["search"], limit=data.get("limit", 50), owner=data.get("owner"),
            allow_stale=allow_stale,
        )
    if operation == "curated":
        return client.curated(allow_stale=allow_stale)


def _registry_install_result(store: Store, data: dict) -> dict | None:
    """Handle registry operations carried by the existing install route."""
    operation = _registry_operation_kind(data)
    if operation is None:
        return None
    if data.get("run") or data.get("preview"):
        raise StoreError("registry operations cannot be combined with run or preview")
    allow_stale = bool(data.get("allow_stale"))
    if operation == "fetch":
        return install.registry_fetch(
            store,
            source=data.get("source"),
            review_id=data.get("review_id"),
            trust_confirmed=data.get("trust_confirmed") is True,
            scope=data.get("scope", "global"),
            expected_hash=data.get("registry_hash"),
            allow_stale=allow_stale,
            external_scan=scan_options(data.get("external_scan")),
        )
    return _registry_read_result(install.registry_client(store), operation, data, allow_stale)


def _validate_payload(store: Store, data: dict, name: str, skill_dir: Path,
                      payload: dict) -> dict:
    """Add the advisory eval harness block to ``/api/validate`` on request.

    Recording is opt-in (``runs``) and only ever writes inside the store's
    ``evals/`` workspace, so the default request keeps its read-only contract.
    """
    if not (data.get("evals") or data.get("runs")):
        return payload
    workspace = evals.ensure_workspace_outside(evals.workspace_for(store.data_dir, name), store.data_dir)
    payload["evals"] = evals.eval_report(
        skill_dir, workspace, name, runs=data.get("runs") or None, iteration=data.get("iteration", 1)
    )
    return payload


def _doctor_query(qs: dict) -> tuple[str, bool, str]:
    scope = _scope_param(qs)
    hygiene = _flag(qs, "hygiene")
    consumer = (qs.get("explain", [""])[0] or "").strip()
    return scope, hygiene, consumer


def _validated_doctor_query(qs: dict) -> tuple[str, bool, str]:
    scope, hygiene, consumer = _doctor_query(qs)
    if hygiene and consumer:
        raise StoreError("doctor hygiene cannot be combined with explain")
    return scope, hygiene, consumer


def _doctor_explain(report: dict, qs: dict, consumer: str, diagnostics_roots) -> None:
    if not consumer:
        return
    report["explain"] = effective.explain(
        consumer,
        (qs.get("project", [""])[0] or "").strip() or None,
        skill=(qs.get("skill", [""])[0] or "").strip() or None,
        allowed_root=diagnostics_roots,
    )


def _doctor_payload(store: Store, qs: dict, diagnostics_roots=None) -> dict:
    """Build the ``/api/doctor`` payload, optionally with the #12 explain block.

    ``explain=CONSUMER`` adds the read-only effective-resolution diagnostic; it
    derives from the filesystem at read time and writes nothing.

    SEC-2/SEC-3: the diagnostic is confined to the store's own data directory.
    ``project`` comes straight from the query string, and without a boundary a
    single unauthenticated GET walked a caller-chosen directory to completion
    and then returned the user's real home directory, ``data_dir``, and the
    complete inventory of skills installed for other agent tools.  The CLI
    passes no boundary (it already runs as the user); HTTP always does.
    """
    scope, hygiene_requested, consumer = _validated_doctor_query(qs)
    report = doctor.doctor_report(store, scope, hygiene=hygiene_requested)
    _doctor_explain(report, qs, consumer, diagnostics_roots)
    return report


def _raw_document_response(handler, name: str, skill_dir: Path) -> None:
    """Send one skill's document as text/plain, or a clean 404.

    D3-1: this route used to call ``read_text(encoding="utf-8")`` directly.
    ``UnicodeDecodeError`` subclasses ``ValueError``, so a non-UTF-8 ``SKILL.md``
    produced a 400 carrying the interpreter's own ``"'utf-8' codec can't decode
    byte ..."`` text, and an unreadable file produced an unhandled 500 --
    while ``GET /api/skills/<name>`` on the same file correctly returned 200.
    An undecodable or unreadable document is now a clean 404: raw bytes are
    served only when they are the document's real text.
    """
    raw = document_text(skill_dir, lossy=False)
    if not raw:
        handler._send_error(404, f"skill '{name}' has no readable SKILL.md")
        return
    handler._send(200, raw.encode("utf-8"), "text/plain; charset=utf-8")


def _apply_token_estimate(record: dict, tok) -> None:
    """Copy one token estimate onto a REST record."""
    record["tokens"] = tok["tokens"]
    record["tokens_method"] = tok["method"]
    record["tokens_pct"] = tok["pct_window"]
    record["chars"] = tok["chars"]


def _row_needs_token_read(row: dict) -> bool:
    """Whether *row* still has to have its document read for an estimate.

    ``Store.list()`` observes every document and derives
    ``tokens``/``tokens_method``/``tokens_pct``/``chars`` from the very bytes it
    just read, so a row that already carries an estimate does not need the
    document opened again.

    The test is ``not row.get("tokens")`` rather than ``"tokens" not in row`` so
    a *zero* estimate still falls through: a document that genuinely occupies no
    context, and a document the loader could not read at all, are then enriched
    rather than reported as a bare zero.
    """
    return not row.get("tokens")


def _enrich_one_row_with_tokens(store: Store, row: dict, physical_root: str) -> None:
    """Stamp the physical-path fields, then estimate tokens only if needed."""
    row.setdefault("physical_root", physical_root)
    if row.get("path"):
        try:
            row.setdefault("physical_path", str(Path(row["path"]).resolve()))
        except OSError:
            row.setdefault("physical_path", str(row["path"]))
    if _row_needs_token_read(row):
        _apply_token_estimate(row, estimate(document_text(store.skills_dir / row["name"])))


def _enrich_rows_with_tokens(store: Store, rows: list[dict], label: str) -> None:
    """Add token estimates to list rows, reporting a failure instead of hiding it.

    BUG-8: four copies of this loop swallowed every failure with
    ``except Exception: pass``, so a crash left a ``200`` payload silently
    missing documented keys (which is what produced BUG-7).  A failure is now
    diagnosed and marked on the rows it affected.

    **A row that already carries an estimate is not re-read** (docs/24 §D1,
    lazy-observations follow-up).  This loop used to re-read every document and
    then *overwrite* the identical value ``Store.list()`` had already derived
    from the same bytes.  Measured on this tree at 1,200 skills:
    ``GET /api/skills?scope=global`` read every document **twice** (2.0x), and
    this function was 17-19% of that route.

    It was also a correctness bug, not only waste.  The second read went through
    :func:`_skill_text`, which decodes with a bare
    ``read_text(encoding="utf-8")`` -- forbidden by SESSION-CONTEXT gotcha #10 --
    so a non-UTF-8 document yielded ``""`` and **clobbered a correct 277-token
    estimate with 0**.  ``GET /api/skills?scope=global`` therefore reported a
    malformed document as occupying no context at all, quietly under-counting it
    against every context-budget figure.  ``scopes._enrich_global_row`` already
    carried exactly this guard; this copy never received it.

    The decision is :func:`_row_needs_token_read`, and the per-row work is
    :func:`_enrich_one_row_with_tokens`, so the fallback stays reachable for the
    rows that need it and disappears for the rows that do not.
    """
    try:
        physical_root = str(store.skills_dir.resolve())
        for row in rows:
            _enrich_one_row_with_tokens(store, row, physical_root)
    except Exception as exc:
        _diagnose(f"{label} token enrichment failed", exc)
        for row in rows:
            row.setdefault("tokens", 0)
            row.setdefault("tokens_method", "unavailable")
            row.setdefault("tokens_pct", 0)
            row.setdefault("chars", 0)


def _enrich_rows_with_catalog(store: Store, rows: list[dict]) -> None:
    """Attach manager-owned tags without changing skill or index authority."""
    enrich_rows(rows, data_dir=store.data_dir)


# Stable machine codes for the one error shape, so a client can branch on
# ``code`` for every route (docs/24 §D3-7).
def _error_payload(status: int, message: object, code: str | None = None) -> dict:
    """The one error shape every route sends.

    ``error`` is always the human message; ``code`` is a stable machine string
    -- the exception's own when it has one, then a shape-specific slug, then the
    status.  Two error families the audit found disagreeing (39 routes with
    ``{"error"}``, the source-update family with ``{"code", "error"}``) are one
    contract now, and a client can branch on ``code`` for every route
    (docs/24 §D3-7).
    """
    payload = getattr(message, "as_dict", lambda: None)()
    if not isinstance(payload, dict):
        payload = {"error": str(message)}
    payload.setdefault("error", str(message))
    payload.setdefault(
        "code",
        code
        or getattr(message, "code", None)
        or _STATUS_CODES.get(status, "error"),
    )
    return payload


_STATUS_CODES = {
    400: "bad_request",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "too_large",
    415: "unsupported_media_type",
    500: "internal_error",
}


_INT_RE = re.compile(r"^[0-9]+$")


def _int_param(qs: dict[str, list[str]], name: str, default: int, *, maximum: int | None = None) -> int:
    """Return a bounded integer query parameter, or raise a clean 400.

    A parameter that cannot be parsed used to be replaced by its default, so
    ``?limit=abc`` answered 200 with 50 rows and a client could not tell its
    request had been ignored (docs/24 §D3-8).  ``^[0-9]+$`` rather than
    ``int()`` because ``int(" 5 ")``, ``int("1_0")`` and ``int("١٢٣")`` all
    succeed -- silently accepting those is the same defect in smaller clothes.
    """
    raw = qs.get(name, [None])[0]
    if raw is None:
        return default
    text = raw.strip()
    if not _INT_RE.match(text):
        raise StoreError(f"{name} must be a whole number, got {raw!r}")
    value = int(text)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _body_param(qs: dict[str, list[str]]) -> bool:
    """Return whether list rows keep their document ``body`` (default yes).

    ``GET /api/skills?body=0`` is an opt-in for callers that render a list and
    fetch the document separately -- the web UI's Library does exactly that.
    On a 2,061-instance library the bodies were 18.9 MB of a 22.7 MB response,
    every one of them discarded by the client.  The default stays ``body=1`` so
    every existing client is unaffected.  Only ``0`` and ``1`` are accepted; any
    other value is a clean 400 rather than a silent default (docs/24 §D3-8).
    """
    values = qs.get("body", [None])
    if len(values) != 1:
        raise StoreError("body must be supplied once as 0 or 1")
    raw = values[0]
    if raw is None:
        return True
    text = raw.strip()
    if text not in ("0", "1"):
        raise StoreError(f"body must be 0 or 1, got {raw!r}")
    return text == "1"


def _list_page(rows: list, qs: dict[str, list[str]]) -> tuple[list, int]:
    include_body = _body_param(qs)
    page, total = _page_rows(rows, qs)
    if not include_body:
        # Coalesced reads give every caller independent rows, so removing a
        # response field cannot alter another request's document snapshot.
        for row in page:
            if isinstance(row, dict):
                row.pop("body", None)
    return page, total


def _scope_summary(store: Store) -> list[dict]:
    """Reuse merged agent rows while keeping global counts filesystem-based."""
    try:
        records = scopes.list_all()
    except StoreError:
        # Scope discovery previously needed no readable SQLite index. Keep
        # that behavior, without rebuilding it as a side effect of this GET.
        return scopes.list_scopes()
    # Global list rows come through the index and can omit newly added,
    # unindexed documents. The scope descriptor must still count those files.
    summary_rows = [record for record in records if record.get("scope") != "global"]
    summary_rows.extend({**record, "scope": "global"} for record in scan_dir(store.skills_dir))
    return scopes.list_scopes(records=summary_rows)


def _window_param(qs: dict[str, list[str]], name: str = "window") -> str:
    """Return the requested context window, or raise a clean 400.

    ``?window=bogus`` and an explicitly blank ``?window=`` used to answer 200
    with Claude's window, so a typo looked like a successful budget report.
    """
    raw = qs.get(name, [DEFAULT_WINDOW])[0]
    if not raw.strip():
        raise StoreError(f"{name} must not be blank")
    return window_name(raw)


def _history_limit(qs: dict[str, list[str]]) -> int:
    value = _int_param(qs, "limit", 50, maximum=MAX_HISTORY_LIMIT)
    if value < 1:
        raise StoreError("limit must be at least 1")
    return value


def _flag(qs: dict[str, list[str]], name: str) -> bool:
    """A boolean query flag: ``1``, ``true`` or ``yes`` (case-insensitive)."""
    return (qs.get(name, [""])[0] or "").strip().lower() in {"1", "true", "yes"}


def _scope_param(qs: dict[str, list[str]]) -> str:
    """The requested scope id; absent or blank means ``global``."""
    return (qs.get("scope", [""])[0] or "").strip() or "global"


def _trash_rows(store, qs: dict[str, list[str]]) -> list[dict]:
    """Trash rows for the requested scope, without changing global behaviour.

    No scope and ``scope=global`` keep ``Store.trash_list()`` exactly.  Every
    other scope reads that agent's sibling trash folder read-only; nothing is
    created by a read.
    """
    scope = _scope_param(qs)
    if scope == "global":
        return store.trash_list()

    return scopes.scope_trash_list(scope)


# Paging parameters a client might reasonably send that this API does not
# implement. They are refused rather than ignored: a caller that pages and
# silently gets the whole set cannot tell its request was ignored (docs/24
# §D3-9).
_UNIMPLEMENTED_PAGING_PARAMS = ("page", "per_page", "perpage", "cursor",
                                "before", "after", "start", "skip", "first")
MAX_PAGE_LIMIT = 500


def _require_installed(record: dict, name: str) -> None:
    """Refuse to serve an index row whose directory is gone.

    ``Store.get()`` deliberately reports ``installed: False`` and ``path:
    None`` for a stale row (STORE-10), and ``doctor()`` still needs to see
    it.  What it must not do is let that row's *stored body* out of the REST
    API: ``list()`` already omits the skill, so answering ``200`` here made
    this the one route serving content the filesystem does not have
    (docs/24 §D3-6).
    """
    if record.get("installed"):
        return
    raise SkillNotFound(
        f"skill '{name}' is not installed; run doctor to see why the index "
        "still has a row for it"
    )


def _page_rows(rows: list, qs: dict[str, list[str]]) -> tuple[list, int]:
    """Apply opt-in ``limit``/``offset`` and return ``(page, total)``.

    Paging is opt-in so the web UI, which asks for ``/api/skills?scope=all``
    with no paging parameters and needs every row, is unaffected.  ``limit`` is
    capped so one request cannot ask for an unbounded page, and an
    out-of-range ``offset`` is an empty page rather than an error.
    """
    unsupported = [name for name in _UNIMPLEMENTED_PAGING_PARAMS if name in qs]
    if unsupported:
        raise StoreError(
            f"paging parameter(s) {', '.join(unsupported)} are not supported; "
            "use limit and offset"
        )
    total = len(rows)
    # ``limit`` is only a limit when the client sent one; 0 is a bad value, not
    # a synonym for "unpaged". ``offset`` applies on its own.
    limit = _int_param(qs, "limit", None, maximum=MAX_PAGE_LIMIT) if "limit" in qs else None
    if limit is not None and limit < 1:
        raise StoreError("limit must be at least 1")
    offset = _int_param(qs, "offset", 0)
    if limit is None:
        return rows[offset:], total
    return rows[offset:offset + limit], total


def _validated_skill_fields(data: dict, *, keep_empty: bool = False) -> dict:
    """Select string fields; PATCH may explicitly clear optional values/body."""
    fields = {}
    for field in _SKILL_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str):
            raise StoreError(f"{field} must be a string")
        if value != "" or keep_empty:
            fields[field] = value
    return fields


def _head_safe_body(command: str, body: bytes) -> bytes:
    """Return the bytes to write for *command*: none at all for HEAD (BUG-9)."""
    return b"" if command == "HEAD" else body


#: BUG-9: the verbs this server routes, advertised on a 405.
_ALLOWED_METHODS = "GET, HEAD, POST, PATCH, PUT, DELETE"
_METHOD_NOT_ALLOWED_BODY = b'{"error": "method not allowed"}'

MAX_BODY_BYTES = MAX_UPLOAD_BYTES
MAX_HISTORY_LIMIT = 200


class WebAppHandler(BaseHTTPRequestHandler):
    server_version = "skillsmgr-webui"

    @property
    def store(self) -> Store:
        return self.server.store  # type: ignore[attr-defined]

    # -- plumbing ---------------------------------------------------------

    def log_message(self, fmt, *args):  # quiet by default
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8",
              extra_headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Added after the status line: a header set before ``send_response``
        # lands in the buffer ahead of it and corrupts the response.
        self._send_extra_headers(extra_headers)
        self._send_security_headers()
        self.end_headers()
        # A HEAD response carries the same headers as the equivalent GET but no
        # body (BUG-9); Content-Length still describes the entity that a GET
        # would have returned.
        self._write_body(_head_safe_body(self.command, body))

    def _send_extra_headers(self, extra_headers: dict[str, str] | None) -> None:
        """Emit per-response headers (``X-Total-Count`` and friends)."""
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)

    def _write_body(self, body: bytes) -> None:
        """Write a response without treating a disconnected client as a bug."""
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browsers and smoke clients can leave while a response is being
            # produced.  The request is already over from the client's point
            # of view; there is no useful error response left to send.
            return

    def _stream_file(self, path: Path, chunk_size: int = 64 * 1024) -> None:
        """Send a file in bounded chunks, tolerating a client that leaves.

        An export is as large as the library, so buffering it whole held one
        full copy in memory per concurrent download, on top of the file.
        """
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Same contract as _write_body: the client is already gone and
            # there is no useful error response left to send.
            return

    def _serve_export(self, qs: dict[str, list[str]]) -> None:
        """Stream an export download without leaving an archive behind.

        A download is a read: the archive is built in a private temporary
        directory and removed afterwards.  This used to call ``export()`` with
        no destination, so every request created
        ``<data>/backups/export-<timestamp>.tar.gz`` and never removed it --
        and `backups/` has no retention, so a browser prefetch, a retry or a
        double click grew it permanently with archives nobody asked to keep
        (docs/24 §D3-3).  The CLI keeps its documented behaviour: it passes no
        destination and still writes to `backups/`.
        """
        scope = _scope_param(qs)
        if scope != "global":
            self._send_error(400, "export is only available for the global scope")
            return
        full = _flag(qs, "full")
        staging = tempfile.mkdtemp(prefix="skillsmgr-webui-export-")
        try:
            archive = self.store.export(
                dest=Path(staging) / f"{'full-export' if full else 'export'}.tar.gz",
                full=full,
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header(
                "Content-Disposition", f'attachment; filename="{archive.name}"'
            )
            self.send_header("Content-Length", str(archive.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self._send_security_headers()
            self.end_headers()
            if self.command != "HEAD":
                self._stream_file(archive)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        # `script-src 'unsafe-eval'` is required by the vendored runtime+compiler
        # build, which compiles the in-DOM template of index.html with
        # `Function(code)()`; removing it needs a build step, which locked
        # constraint 4 forbids (SEC-4 — reasoned trade-off recorded in
        # docs/08-web-ui.md).  `'unsafe-inline'` must never join script-src.
        #
        # `form-action` does not fall back to `default-src`, so an injected
        # <form action="https://…"> would otherwise be allowed to submit (SEC-5).
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'none'",
        )

    def _send_json(self, obj, status: int = 200,
                   extra_headers: dict[str, str] | None = None) -> None:
        self._send(status, json_bytes(obj), extra_headers=extra_headers)

    def _send_page(self, rows: list, qs: dict[str, list[str]]) -> None:
        """Send one page of ``rows`` with an ``X-Total-Count`` header.

        The header is set before the body so ``HEAD`` reports the size of the
        page a ``GET`` would have returned.
        """
        page, total = _list_page(rows, qs)
        self._send_json(page, extra_headers={"X-Total-Count": str(total)})

    def _send_error(self, status: int, message: str, code: str | None = None) -> None:
        """Send the one error shape every route uses.

        ``{"error": message, "code": <stable string>}``.  ``error`` is always
        present so a client can always branch on it; ``code`` is the exception's
        own stable code when it has one (``SourceUpdateError`` and friends) and
        otherwise a fixed slug for the status, so the two families the audit
        found disagreeing are one contract now (docs/24 §D3-7).
        """
        self._send_json(_error_payload(status, message, code), status)

    def _read_body(self, limit: int = MAX_BODY_BYTES) -> bytes:
        raw_length = self.headers.get("Content-Length") or "0"
        try:
            length = int(str(raw_length).strip())
        except ValueError:
            raise StoreError("invalid Content-Length")
        if length < 0:
            raise StoreError("invalid Content-Length")
        if length > limit:
            # Do not wait for bytes the peer may never send. Closing also
            # prevents unconsumed bytes becoming a request on this connection.
            self.close_connection = True
            raise RequestError(413, "request body too large")
        return self.rfile.read(length) if length else b""

    def _body_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        return parse_json_object(raw, self.headers.get("Content-Type", ""))


    # -- routing ----------------------------------------------------------

    def _serve(self, *steps) -> None:
        """Validate the request, run each step, and map any failure to one response."""
        try:
            self._validate_request()
            for step in steps:
                step()
        except Exception as exc:
            self._handle_exception(exc)

    def do_GET(self):
        self._serve(self._route_get)

    def do_POST(self):
        self._serve(self._require_post_media_type, self._route_post)

    def do_PATCH(self):
        self._serve(self._route_patch)

    def do_DELETE(self):
        self._serve(self._route_delete)

    def do_PUT(self):
        self._serve(self._route_put)

    def do_HEAD(self):
        """Answer HEAD like the equivalent GET, headers only (BUG-9).

        The stdlib's default handler answered HEAD/OPTIONS/TRACE with a 501 HTML
        page that carried **no** security headers at all, so those verbs
        bypassed the whole response policy.  ``_send`` suppresses the body.
        """
        self._serve(self._route_get)

    def do_OPTIONS(self):
        self._serve(self._method_not_allowed)

    def do_TRACE(self):
        self._serve(self._method_not_allowed)

    def _method_not_allowed(self) -> None:
        """Refuse an unrouted verb with the standard policy and headers."""
        self.send_response(405)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Allow", _ALLOWED_METHODS)
        self.send_header("Content-Length", str(len(_METHOD_NOT_ALLOWED_BODY)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        self._write_body(_METHOD_NOT_ALLOWED_BODY)

    def _require_post_media_type(self) -> None:
        """Every POST must declare ``application/json``, body or not (R9/S4).

        Bodyless mutations (``/api/trash/purge``, ``/api/rebuild``,
        ``/api/resync``, enable/disable, trash restore) skipped the check
        because they never parsed a body, so a ``text/plain`` POST -- one a
        cross-site form can send without a preflight -- emptied the trash.
        Origin and Fetch-Metadata checks still apply first; this removes the
        "simple request" shape altogether.  The multipart source-update upload
        is the one POST that carries another media type, and its route
        enforces ``multipart/form-data`` itself.
        """
        if self._parts() == ["api", "source-updates", "reviews"]:
            return
        media = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            raise RequestError(415, "POST requests must declare Content-Type: application/json")

    def _handle_exception(self, exc: Exception) -> None:
        if isinstance(exc, SkillNotFound):
            self._send_error(404, str(exc))
        elif isinstance(exc, StoreError):
            self._send_error(getattr(exc, "status", 400), exc)
        elif isinstance(exc, ValueError):
            self._send_error(400, str(exc))
        else:
            print(f"webui internal error: {exc!r}", file=sys.stderr)
            self._send_error(500, "internal error")


    def _validate_request(self) -> None:
        validate_request(
            self.headers,
            self.server.allowed_hosts,  # type: ignore[attr-defined]
            self.server.allowed_origins,  # type: ignore[attr-defined]
        )

    def _parts(self) -> list[str]:
        path = urlparse(self.path).path
        # Decode each segment after splitting so an encoded slash remains part
        # of the user-controlled name and reaches the canonical name guard.
        return [unquote(p) for p in path.split("/") if p]

    # -- static -----------------------------------------------------------

    @staticmethod
    def _classic_parts(parts: list[str]) -> list[str]:
        """Keep classic's relative assets together under its explicit URL."""
        return parts[1:] if parts[:1] == ["classic"] else parts

    @staticmethod
    def _static_rel(parts: list[str]) -> str:
        """Map URL segments to a path under the web UI directory.

        Both interfaces retain their existing asset directories. The classic
        URL prefix is an alias for the original files, not a second copy.
        """
        parts = WebAppHandler._classic_parts(parts)
        rel = parts[0] if parts else "index.html"
        if rel in ("static", "v2") and len(parts) >= 2:
            return rel + "/" + "/".join(parts[1:])
        if rel == "v2":
            return "v2/index.html"
        return rel or "index.html"

    def _redirect_v2(self, parts: list[str]) -> bool:
        if parts == ["v2"] and not urlparse(self.path).path.endswith("/"):
            # The v2 page loads ``styles.css``, ``model.js`` and ``app.js`` by
            # relative path. Served at ``/v2`` the browser resolves those
            # against ``/`` and mounts the *classic* app into v2's markup -- a
            # blank page. Redirect to a fixed local directory, preserving
            # the query. The v2 UI routes by ``#fragment``,
            # which browsers carry across a redirect.
            query = urlparse(self.path).query
            location = "/v2/" + ("?" + query if query else "")
            self._send(308, b"", "text/plain; charset=utf-8",
                       extra_headers={"Location": location})
            return True
        return False

    # Which interface ``/`` opens is a product choice that may change, so it is
    # a temporary 307: a browser must not cache it forever, and Python 3.10's
    # urllib follows 307 but not 308 (it raised on every ``/`` request there).
    # Adding a slash to ``/classic`` never changes, so that stays a 308.
    _ENTRY_REDIRECTS = {"/": ("/v2/", 307), "/index.html": ("/v2/", 307), "/classic": ("/classic/", 308)}

    def _redirect_document(self, parts: list[str]) -> bool:
        """Promote v2 while preserving explicit classic and v2 entry points."""
        parsed = urlparse(self.path)
        entry = self._ENTRY_REDIRECTS.get(parsed.path)
        if entry is None:
            return self._redirect_v2(parts)
        destination, status = entry
        location = destination + ("?" + parsed.query if parsed.query else "")
        self._send(status, b"", "text/plain; charset=utf-8", extra_headers={"Location": location})
        return True

    def _serve_static(self) -> bool:
        parts = self._parts()
        if parts and parts[0] == "api":
            return False
        if self._redirect_document(parts):
            return True
        rel = self._static_rel(parts)
        candidate = (_WEBUI_DIR / rel).resolve()
        inside = candidate.is_relative_to(_WEBUI_DIR)
        if not inside or not candidate.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return True
        self._send(
            200,
            candidate.read_bytes(),
            _STATIC_TYPES.get(candidate.suffix, "application/octet-stream"),
        )
        return True

    # -- GET routes -------------------------------------------------------

    def _route_source_update_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        if len(parts) == 4 and parts[:3] == ["api", "source-updates", "reviews"]:
            self._send_json(read_update_review(self.store.data_dir, parts[3]))
            return True
        if parts == ["api", "source-updates", "snapshots"]:
            name = (qs.get("name", [""])[0] or "").strip()
            scope = _scope_param(qs)
            target_path = qs.get("target_path", [None])[0] or None
            snapshots = list_update_snapshots(self.store.data_dir, name, scope, target_path=target_path)
            self._send_json({"name": name, "scope": scope, "snapshots": snapshots})
            return True
        return False

# -- GET routes -------------------------------------------------------

    def _route_library_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve the root/workspace discovery reads.

        Three exact two-segment paths that answer "what can this manager see":
        the agent scopes, the manager-owned catalog, and the adapter catalog
        with an optional contained project.  They are one guard because they
        share a shape and a purpose, not because they share code.
        """
        if parts == ["api", "scopes"]:
            self._send_json(_scope_summary(self.store))
            return True
        if parts == ["api", "catalog"]:
            self._send_json(load_catalog(self.store.data_dir))
            return True
        if parts == ["api", "workspaces"]:
            project = (qs.get("project", [""])[0] or "").strip() or None
            roots = getattr(self.server, "diagnostics_roots", None) or [self.store.data_dir]
            self._send_json(workspaces_payload(project, roots))
            return True
        return False

    def _route_profile_preview_get(self, parts: list[str]) -> bool:
        """Serve ``GET /api/catalog/profiles/<name>/preview``.

        The only reason this is not in ``_route_library_get`` is its shape: a
        five-segment path, so it cannot be confused with the exact two-segment
        reads beside it.
        """
        if len(parts) == 5 and parts[:3] == ["api", "catalog", "profiles"] and parts[4] == "preview":
            profile_name = parts[3]
            profile = load_catalog(self.store.data_dir)["profiles"].get(profile_name)
            if profile is None:
                raise SkillNotFound(f"profile '{profile_name}' not found")
            self._send_json({"name": profile_name, **profile_preview(profile, scopes.list_all())})
            return True
        return False

    def _route_skills_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/skills`` -- the list/search page for every scope.

        Four scope modes and a search variant in each.  Reads are per scope:
        ``all`` merges, a named agent scope reads that root, and the default
        goes through the scope adapter so wildcard validation and body-aware
        ranking share one ``StoreError`` seam.  Token and catalog enrichment
        run per branch because the merged and agent rows already carry their
        own token counts.
        """
        if parts != ["api", "skills"]:
            return False
        _body_param(qs)  # reject a malformed ``body`` before scanning anything
        scope = (qs.get("scope", [""])[0] or "").strip()
        q = (qs.get("q", [""])[0] or "").strip()
        if scope == "all":
            if q:

                rows = scopes.search_all(q, scope_id="all", store=self.store)
            else:

                rows = scopes.list_all()
            _enrich_rows_with_catalog(self.store, rows)
            self._send_page(rows, qs)
            return True
        if scope and scope != "global":

            if q:
                rows = scopes.search_all(q, scope_id=scope)
            else:
                rows = scopes.scan_scope(scope)
            _enrich_rows_with_catalog(self.store, rows)
            self._send_page(rows, qs)
            return True
        # scope == "" or "global": use the scope adapter so wildcard
        # validation and body-aware ranking share one StoreError seam.
        if q:

            rows = scopes.search_all(q, scope_id="global", store=self.store)
            for r in rows:
                r.setdefault("scope", "global")
                r.setdefault("scope_label", "Global")
            # Add token enrichment from actual files
            _enrich_rows_with_tokens(self.store, rows, "all-scope list")
            _enrich_rows_with_catalog(self.store, rows)
            self._send_page(rows, qs)
        else:
            rows = self.store.list()
            for r in rows:
                r.setdefault("scope", "global")
                r.setdefault("scope_label", "Global")
            # Token enrichment for list rows
            _enrich_rows_with_tokens(self.store, rows, "global list")
            _enrich_rows_with_catalog(self.store, rows)
            self._send_page(rows, qs)
        return True

    def _route_search_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/search`` -- ranked rows, no paging.

        Distinct from ``GET /api/skills?q=`` because it is unpaged.  The query
        bound is enforced by ``scopes.search_all`` before any work.
        """
        if parts != ["api", "search"]:
            return False
        scope = _scope_param(qs)
        rows = scopes.search_all(qs.get("q", [""])[0], scope_id=scope, store=self.store)
        _enrich_rows_with_catalog(self.store, rows)
        self._send_json(rows)
        return True

    def _route_skill_raw_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/skills/<name>/raw`` -- the document as text/plain.

        The global branch resolves through ``Store.get()`` before it builds any
        filesystem path, so the decoded path segment is validated by the
        canonical name guard before it can reach a read.
        """
        if len(parts) != 4 or parts[:2] != ["api", "skills"] or parts[3] != "raw":
            return False
        scope = _scope_param(qs)
        if scope != "global":
            raw = scopes.get_raw(scope, parts[2])
            self._send(200, raw.encode("utf-8"), "text/plain; charset=utf-8")
            return True
        # Resolve through Store.get() first so the decoded path segment is
        # validated before it can be used for a filesystem read.
        record = self.store.get(parts[2])
        _require_installed(record, parts[2])
        _raw_document_response(self, parts[2], Path(record["path"]))
        return True

    def _route_skill_detail_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/skills/<name>`` -- one full record with counts.

        A row whose directory is gone answers 404 rather than its stored body
        (docs/24 §D3-6).
        """
        if len(parts) != 3 or parts[:2] != ["api", "skills"]:
            return False
        record = scopes.get_skill(_scope_param(qs), parts[2])
        _enrich_rows_with_catalog(self.store, [record])
        self._send_json(record)
        return True

    def _route_templates_get(self, parts: list[str]) -> bool:
        """Read stored templates without allowing a template link to escape data."""
        if parts == ["api", "templates"]:
            self._send_json({"templates": list_templates(self.store.templates_dir)})
            return True
        if len(parts) != 3 or parts[:2] != ["api", "templates"]:
            return False
        name = parts[2]
        entry = template_path(self.store.templates_dir, name)
        try:
            contained_path(self.store.data_dir, "templates", entry.name)
            if entry.is_symlink():
                raise StoreError("Linked templates cannot be read; use a regular template file.")
            body = read_template(self.store.templates_dir, name)
        except FileNotFoundError:
            raise RequestError(404, "Template not found.") from None
        except (OSError, UnicodeError, ValueError) as exc:
            raise StoreError("Template could not be read as a contained UTF-8 document.") from exc
        self._send_json({"name": name, "body": body})
        return True

    def _route_collection_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve the small exact-path reads: trash, templates, doctor, export.

        Each is a two-segment path with no branching of its own -- one call and
        a response -- so they share one guard rather than earning a method
        each.  ``/api/export`` keeps its own implementation in
        ``_serve_export`` because streaming it is not a one-liner.
        """
        if parts == ["api", "trash"]:
            self._send_json(_trash_rows(self.store, qs))
            return True
        if self._route_templates_get(parts):
            return True
        if parts == ["api", "doctor"]:
            self._send_json(
                _doctor_payload(
                    self.store, qs, getattr(self.server, "diagnostics_roots", None) or [self.store.data_dir]
                )
            )
            return True
        if parts == ["api", "export"]:
            self._serve_export(qs)
            return True
        return False

    def _route_history_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/history``, plus its ``snapshots=1`` variant."""
        if parts != ["api", "history"]:
            return False
        name = qs.get("name", [None])[0]
        limit = _history_limit(qs)
        if _flag(qs, "snapshots") and name:
            scope = _scope_param(qs)
            snapshots = scopes.list_snapshots_for(scope, name)
            self._send_json({"name": name, "scope": scope, "snapshots": snapshots})
            return True
        self._send_json(self.store.history(name=name, limit=limit))
        return True

    def _route_stats_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/stats`` -- store counts plus scope/token budgets.

        BUG-8/BUG-7: the enrichment below used to swallow every failure, so a
        crash answered 200 with documented keys missing.  Each step now
        reports itself through ``degraded`` and fills the keys the UI depends
        on, so a client is never handed a half-record.
        """
        if parts != ["api", "stats"]:
            return False
        st = self.store.stats()
        win_qs = _window_param(qs)
        try:
            records = scopes.list_all()
            summary = scopes.list_scopes(records=records)
            st["scopes"] = summary
            st["all_total"] = sum(s["count"] for s in summary)
            totals = aggregate(records, win_qs)
            st["all_tokens"] = sum(s.get("tokens", 0) for s in summary)
            st["all_avg_tokens"] = (st["all_tokens"] // st["all_total"]) if st["all_total"] else 0
            st["window"] = win_qs
            st["window_tokens"] = totals["window_tokens"]
            st["all_pct_window"] = round(st["all_tokens"] / totals["window_tokens"] * 100, 1)
            st["largest"] = totals["largest"]
            st["has_tiktoken"] = totals["has_tiktoken"]
        except Exception as exc:
            # BUG-8/BUG-7: this is the swallow that returned a 200 payload
            # with documented keys missing.  Report it and fill the keys the
            # UI depends on so the client cannot be handed a half-record.
            _diagnose("stats scope enrichment failed", exc)
            for key, fallback in (
                ("scopes", []), ("all_total", 0), ("all_tokens", 0),
                ("all_avg_tokens", 0), ("window_tokens", 0),
                ("all_pct_window", 0), ("largest", []),
            ):
                st.setdefault(key, fallback)
            st.setdefault("degraded", []).append("scopes")
        self._send_json(st)
        return True

    def _route_tokens_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``GET /api/tokens`` -- one estimate or a scope aggregate.

        Three modes: raw ``text``, one named skill (resolved across scopes when
        no scope is given), or an aggregate over a scope.  The named mode is
        the only one that touches the filesystem, so it is split out into
        ``_tokens_record`` and ``_tokens_document`` below.
        """
        if parts != ["api", "tokens"]:
            return False
        win = _window_param(qs)
        name = (qs.get("name", [""])[0] or "").strip()
        scope = (qs.get("scope", ["all"])[0] or "all").strip()
        text = (qs.get("text", [""])[0] or "")
        if text:
            self._send_json(estimate(text, window=win))
            return True
        if name:
            self._send_json(estimate(scopes.record_text(scopes.find_skill(name, scope)), window=win))
            return True
        records = scopes.list_all() if scope in ("all", "") else scopes.scan_scope(scope)
        self._send_json(aggregate(records, win))
        return True


    def _route_tail_get(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """The last GET guards: token estimates, then the AI routes."""
        return self._route_tokens_get(parts, qs) or self._route_ai_get(parts)

    def _route_ai_get(self, parts: list[str]) -> bool:
        """Serve the read-only AI routes: settings (never the key) and saved runs."""
        if parts[:2] != ["api", "ai"]:
            return False
        data_dir = self.store.data_dir
        if parts == ["api", "ai", "settings"]:
            self._send_json(ai.public_settings(data_dir))
        elif len(parts) == 4 and parts[2] == "prompt-sets":
            self._send_json(ai_skills.read_prompt_set(data_dir, parts[3]))
        elif parts == ["api", "ai", "runs"]:
            self._send_json({"runs": ai_skills.list_runs(data_dir)})
        elif len(parts) == 4 and parts[2] == "runs":
            self._send_json(ai_skills.read_run(data_dir, parts[3]))
        else:
            return False
        return True

    def _route_get(self):
        """Dispatch ``GET`` to one route guard, in order.

        Every guard below answers the request itself and returns ``True``, or
        returns ``False`` without touching the socket.  The order is the
        original order and the guards are mutually exclusive: each exact route
        is a two-segment path and each shape-matched route needs three or more,
        so no entry can shadow another.  Anything unclaimed is a JSON 404.
        """
        parts = self._parts()
        if self._serve_static():
            return
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if self._route_source_update_get(parts, qs):
            return
        if self._route_library_get(parts, qs):
            return
        if self._route_profile_preview_get(parts):
            return
        if self._route_skills_get(parts, qs):
            return
        if self._route_search_get(parts, qs):
            return
        if self._route_skill_raw_get(parts, qs):
            return
        if self._route_skill_detail_get(parts, qs):
            return
        if self._route_collection_get(parts, qs):
            return
        if self._route_history_get(parts, qs):
            return
        if self._route_stats_get(parts, qs):
            return
        if self._route_tail_get(parts, qs):
            return
        self._send_error(404, "unknown endpoint", code="unknown_endpoint")
    # -- POST routes ------------------------------------------------------


    def _route_batch_post(self, parts: list[str]) -> bool:
        if parts == ["api", "batch", "preview"]:
            self._send_json(batch.preview(self._body_json()))
            return True
        if parts == ["api", "batch", "execute"]:
            self._send_json(batch.execute(self._body_json()))
            return True
        return False

    def _route_catalog_post(self, parts: list[str]) -> bool:
        if parts == ["api", "catalog", "tags"]:
            data = self._body_json()
            names = data.get("names")
            values = data.get("tags")
            if not isinstance(names, list) or not isinstance(values, list):
                raise StoreError("tag updates require names and tags lists")
            self._send_json(update_tags(self.store.data_dir, names, data.get("operation", "add"), values))
            return True
        if parts != ["api", "catalog", "profiles"]:
            return False
        data = self._body_json()
        name = data.pop("name", None)
        if not isinstance(name, str):
            raise StoreError("profile name must be a string")
        self._send_json(save_profile(self.store.data_dir, name, data))
        return True

    def _route_new_post(self, parts: list[str]) -> bool:
        if parts[:2] == ["api", "batch"]:
            return self._route_batch_post(parts)
        if parts[:2] == ["api", "catalog"]:
            return self._route_catalog_post(parts)
        return False

    @staticmethod
    def _multipart_fields(file_parts: list[dict]) -> tuple[dict, list[dict]]:
        fields: dict[str, str] = {}
        files: list[dict] = []
        for part in file_parts:
            if part.get("filename"):
                files.append(part)
            else:
                fields[part.get("name", "")] = (part.get("content") or b"").decode("utf-8")
        return fields, files

    def _route_source_update_post(self, parts: list[str]) -> bool:
        if parts == ["api", "source-updates", "reviews"]:
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("multipart/form-data"):
                raise RequestError(415, "multipart/form-data request body required")
            boundary = re.search(r"boundary=([^;]+)", content_type)
            if not boundary:
                raise StoreError("multipart boundary missing")
            fields, files = self._multipart_fields(
                parse_multipart(self._read_body(), boundary.group(1).strip('"'))
            )
            options = scan_options(fields.get("external_scan"))
            with staged_single_skill(files) as source_dir:
                result = prepare_local_update(
                    self.store.data_dir, fields.get("name", ""), fields.get("scope", "global"),
                    source_dir, target_path=fields.get("target_path") or None,
                    source_value="browser-upload", external_scan=options,
                )
            self._send_json(result, 201 if result.get("review_state") == "pending" else 200)
            return True
        if parts == ["api", "source-updates", "reviews", "from-snapshot"]:
            data = self._body_json()
            result = prepare_snapshot_update(
                self.store.data_dir, data.get("name", ""), data.get("scope", "global"),
                data.get("snapshot_id", ""), target_path=data.get("target_path"),
                external_scan=scan_options(data.get("external_scan")),
            )
            self._send_json(result, 201 if result.get("review_state") == "pending" else 200)
            return True
        if len(parts) == 5 and parts[:3] == ["api", "source-updates", "reviews"] and parts[4] == "commit":
            data = self._body_json()
            result = commit_update_review(
                self.store.data_dir, parts[3], name=data.get("name", ""),
                scope=data.get("scope", "global"), target_path=data.get("target_path"),
                approve=data.get("approve") is True,
            )
            self._send_json(result)
            return True
        return False

    def _route_sync_post(self, parts: list[str]) -> bool:
        """Serve ``POST /api/sync`` -- copy one skill between scopes.

        Every field is validated before any copy runs, so a refused request
        has not moved a skill (docs/24 §D3-8).
        """
        if parts != ["api", "sync"]:
            return False
        data = self._body_json()
        raw_name = data.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise StoreError("name must be a string")
        name = raw_name.strip()
        raw_from_scope = data.get("from_scope") or "global"
        if not isinstance(raw_from_scope, str):
            raise StoreError("from_scope must be a string")
        from_scope = raw_from_scope.strip() or "global"
        to_scopes = batch.requested_scopes(data)
        force = bool(data.get("force"))
        self._send_json(scopes.sync_skill(name, from_scope, to_scopes, force=force))
        return True

    def _route_install_post(self, parts: list[str]) -> bool:
        """Serve ``POST /api/install`` -- registry reads and runner install.

        Three families share this path: the bounded skills.sh operations
        (browse/search/curated/fetch), an offline preview of the command the
        runner *would* run, and the execution itself.  Only the last one runs a
        subprocess, and only for an explicit ``run``.
        """
        if parts != ["api", "install"]:
            return False
        data = self._body_json()
        result = _registry_install_result(self.store, data)
        if result is not None:
            self._send_json(result)
            return True
        source, runner, cmd_parts = _install_command(data)
        cmd_str = " ".join(cmd_parts)
        if not data.get("run"):
            self._send_json(_install_preview_payload(self.store, data, source, cmd_str, runner))
            return True
        try:
            result = install.run_install(cmd_parts)
        except install.InstallTimeoutError as exc:
            self._send_json({"command": cmd_str, "error": str(exc), "executed": True}, 500)
            return True
        self._send_json({
            "command": cmd_str, "runner": runner, "source": source, "executed": True,
            **result,
        })
        return True


    def _route_skill_write_post(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``POST /api/skills`` -- create one skill, 201 on success.

        Name and description are required before anything is written, and the
        remaining metadata is validated by the shared field guard rather than
        per-route, so a scalar where a list belongs is a clean 400 and not a
        half-created skill.
        """
        if parts != ["api", "skills"]:
            return False
        scope = _scope_param(qs)
        data = self._body_json()
        name = data.pop("name", None)
        description = data.pop("description", None)
        if not isinstance(name, str) or not name.strip():
            raise StoreError("name must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise StoreError("description must be a non-empty string")
        fields = _validated_skill_fields(data)
        self._send_json(scopes.create_skill(scope, name, description, **fields), 201)
        return True

    def _route_skill_toggle_post(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``POST /api/skills/<name>/disable`` and ``/enable``.

        The response echoes the verb that was applied, so a client can confirm
        which transition happened without spending a second read.
        """
        if len(parts) != 4 or parts[:2] != ["api", "skills"] or parts[3] not in ("disable", "enable"):
            return False
        name = parts[2]
        scope = _scope_param(qs)
        if scope != "global":
            self._send_json(scopes.toggle_skill(scope, name, enable=(parts[3] == "enable")))
            return True
        action = getattr(self.store, parts[3])
        action(name)
        self._send_json({"name": name, parts[3]: True})
        return True

    def _route_trash_post(self, parts: list[str], qs: dict[str, list[str]]) -> bool:
        """Serve ``/api/trash`` -- purge, restore, and rollback to a snapshot.

        A path under ``/api/trash`` that is neither ``purge`` nor a single
        name is a JSON 404 rather than a silently ignored mutation.
        """
        if parts[:2] != ["api", "trash"]:
            return False
        if len(parts) == 3 and parts[2] == "purge":
            self._send_json(self.store.purge_trash())
            return True
        if len(parts) == 3:
            self._restore_trash_post(parts[2], qs)
            return True
        self._send_error(404, "unknown endpoint", code="unknown_endpoint")
        return True

    def _restore_trash_post(self, name: str, qs: dict[str, list[str]]) -> None:
        """Restore one name from the global store or an agent's trash folder.

        A ``snapshot`` query keeps the historical snapshot rollback.  Without
        it, ``global`` restores through the Store exactly as before, and an
        agent scope restores the exact trashed copy named by the JSON
        ``trash_path`` (or that skill's newest trashed copy).
        """
        snapshot = qs.get("snapshot", [None])[0]
        scope = _scope_param(qs)
        if snapshot:
            self._send_json(scopes.restore_snapshot(scope, name, snapshot))
            return
        if scope != "global":
            trash_path = self._body_json().get("trash_path")
            if trash_path is not None and not isinstance(trash_path, str):
                raise StoreError("trash_path must be a string")
            self._send_json(scopes.restore_trashed(scope, name, trash_path=trash_path))
            return
        self._send_json(self.store.restore(name))

    def _route_templates_post(self, parts: list[str]) -> bool:
        """Serve ``POST /api/templates`` -- create a template, 201 on success.

        A duplicate name or an invalid one is reported as the same
        ``StoreError`` shape as every other refusal, never as a raw
        ``FileExistsError`` or ``ValueError``.
        """
        if parts != ["api", "templates"]:
            return False
        data = self._body_json()
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise StoreError("template name must be a non-empty string")
        body = data.get("body")
        if body is not None and not isinstance(body, str):
            raise StoreError("template body must be a string")
        try:
            path = create_template(self.store.templates_dir, name, data.get("body") or None)
        except FileExistsError as exc:
            raise StoreError(str(exc)) from exc
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        self._send_json({"name": name, "path": str(path)}, 201)
        return True

    def _route_validate_post(self, parts: list[str]) -> bool:
        """Serve ``POST /api/validate`` -- validate one skill, optionally evals.

        The record is resolved through the store or the named agent scope
        first, so a name that fails the canonical guard never reaches the
        validator.
        """
        if parts != ["api", "validate"]:
            return False
        data = self._body_json()
        raw_name = data.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise StoreError("skill name must be a non-empty string")
        name = raw_name.strip()
        requested_scope = data.get("scope", "global")
        if not isinstance(requested_scope, str) or not requested_scope.strip():
            raise StoreError("scope must be a non-empty string")
        requested_scope = requested_scope.strip()
        if requested_scope == "global":
            record = self.store.get(name)
        else:

            record = scopes.get_skill(requested_scope, name)
        if not record.get("path"):
            raise StoreError(f"skill '{name}' has no directory on disk")
        result = validate_skill(name, Path(record["path"]))
        self._send_json(
            _validate_payload(
                self.store,
                data,
                name,
                Path(record["path"]),
                {
                    "valid": result.valid,
                    "issues": [
                        {"level": issue.level, "key": issue.key, "message": issue.message}
                        for issue in result.issues
                    ],
                },
            )
        )
        return True

    def _route_index_post(self, parts: list[str]) -> bool:
        """Serve ``POST /api/rebuild`` and ``/api/resync``.

        Both re-derive the SQLite index from the filesystem and touch no skill
        document; the index is a rebuildable cache, never the source of truth.
        """
        if parts == ["api", "rebuild"]:
            self._send_json(self.store.db_rebuild())
            return True
        if parts == ["api", "resync"]:
            self._send_json(self.store.resync())
            return True
        return False

    def _route_tail_post(self, parts: list[str]) -> bool:
        """The last POST guards: index maintenance, then the AI routes."""
        return self._route_index_post(parts) or self._route_ai_post(parts)

    def _route_ai_post(self, parts: list[str]) -> bool:
        """Serve the AI routes that save settings or call the user's model.

        The loopback binding is the only boundary for these routes, exactly as
        for every other route: any process on this machine that can reach the
        port can spend the configured key up to its token caps (docs/39 §4).
        """
        if parts[:2] != ["api", "ai"] or len(parts) != 3:
            return False
        data_dir = self.store.data_dir
        handlers = {
            "settings": lambda body: ai.save_settings(data_dir, body),
            "test-connection": lambda body: ai.test_connection(data_dir),
            "suggest-profile": lambda body: ai_profiles.suggest_profile(
                data_dir, body, allowed_roots=getattr(self.server, "diagnostics_roots", None) or [data_dir]),
            "concise": lambda body: ai_concise.concise_skill(data_dir, body),
            "draft-skill": lambda body: ai_draft.draft_skill(data_dir, body),
            "trigger-test": lambda body: ai_skills.trigger_test(data_dir, body),
            "improve-description": lambda body: ai_skills.improve_description(data_dir, body),
            "overlap-judge": lambda body: ai_overlap.overlap_judge(data_dir, body),
            "fit-budget": lambda body: ai_budget.fit_budget(data_dir, body),
            "review-briefing": lambda body: ai_review.review_briefing(data_dir, body),
            "prompt-sets": lambda body: ai_skills.save_prompt_set(data_dir, body),
            "evals": lambda body: ai_evals.run_evals(self.store, body),
            "ask": lambda body: ai_ask.ask_library(data_dir, body),
            "porting-notes": lambda body: ai_port.porting_notes(data_dir, body),
        }
        handler = handlers.get(parts[2])
        if handler is None:
            return False
        return self._run_ai_handler(handler)

    def _run_ai_handler(self, handler) -> bool:
        body = self._body_json()
        try:
            with ai.client_disconnect_check(lambda: _client_disconnected(self.connection),
                                            {k: body[k][:128] for k in ("scope", "name")
                                             if isinstance(body.get(k), str)}):
                result = handler(body)
        except ai.ClientDisconnected:
            return True
        self._send_json(result)
        return True

    def _route_post(self):
        """Dispatch ``POST`` to one route guard, in order.

        Same contract as ``_route_get``: each guard answers the request and
        returns ``True``, or returns ``False`` untouched.  The two guards
        already extracted from the POST router -- ``_route_source_update_post``
        and ``_route_new_post`` -- keep their leading position, and the
        remaining predicates are mutually exclusive (the only prefix catch-all
        is ``/api/trash``, which no other predicate matches).  Anything
        unclaimed is a JSON 404.
        """
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if self._route_source_update_post(parts):
            return
        if self._route_new_post(parts):
            return
        if self._route_sync_post(parts):
            return
        if self._route_install_post(parts):
            return
        if self._route_skill_write_post(parts, qs):
            return
        if self._route_skill_toggle_post(parts, qs):
            return
        if self._route_trash_post(parts, qs):
            return
        if self._route_templates_post(parts):
            return
        if self._route_validate_post(parts):
            return
        if self._route_tail_post(parts):
            return
        self._send_error(404, "unknown endpoint", code="unknown_endpoint")
    # -- PATCH routes -----------------------------------------------------

    def _route_patch(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            scope = _scope_param(qs)
            data = self._body_json()
            fields = _validated_skill_fields(data, keep_empty=True)
            self._send_json(scopes.edit_skill(scope, parts[2], **fields))
        else:
            self._send_error(404, "unknown endpoint", code="unknown_endpoint")

    # -- DELETE routes ----------------------------------------------------

    def _route_source_update_delete(self, parts: list[str]) -> bool:
        if len(parts) == 4 and parts[:3] == ["api", "source-updates", "reviews"]:
            self._send_json(cancel_update_review(self.store.data_dir, parts[3]))
            return True
        return False

    def _delete_route(self, parts: list[str], qs: dict[str, list[str]]) -> None:
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            purge = _flag(qs, "purge")
            scope = _scope_param(qs)
            self._send_json(scopes.remove_skill(scope, parts[2], purge=purge))
        elif len(parts) == 4 and parts[:3] == ["api", "catalog", "profiles"]:
            self._send_json(delete_profile(self.store.data_dir, parts[3]))
        else:
            self._send_error(404, "unknown endpoint", code="unknown_endpoint")

    def _route_delete(self):
        parts = self._parts()
        if self._route_source_update_delete(parts):
            return
        self._delete_route(parts, parse_qs(urlparse(self.path).query, keep_blank_values=True))

    # -- PUT routes -------------------------------------------------------

    def _route_put(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        ctype = self.headers.get("Content-Type", "")
        if parts == ["api", "import"] and ctype.lower().startswith("multipart/form-data"):
            boundary_m = re.search(r"boundary=([^;]+)", ctype)
            if not boundary_m:
                self._send_error(400, "multipart boundary missing")
                return
            file_parts = parse_multipart(self._read_body(), boundary_m.group(1).strip('"'))
            uploaded = upload_folder(file_parts, self.store.add)
            self._send_json(uploaded)
        elif parts == ["api", "import"]:
            filename = os.path.basename(
                qs.get("filename", ["skills-import.tar.gz"])[0] or "skills-import.tar.gz"
            )
            if not filename.endswith((".tar.gz", ".tgz", ".tar", ".zip")):
                self._send_error(400, "unsupported archive type (use .tar.gz/.tgz/.tar/.zip)")
                return
            force = _flag(qs, "force")
            full = _flag(qs, "full")
            raw = self._read_body()
            if not raw:
                self._send_error(400, "empty archive body")
                return
            target = Path(tempfile.mkdtemp(prefix="skillsmgr-webui-")) / filename
            try:
                target.write_bytes(raw)
                result = self.store.import_(target, force=force, full=full)
            finally:
                shutil.rmtree(target.parent, ignore_errors=True)
            self._send_json(result)
        else:
            self._send_error(404, "unknown endpoint", code="unknown_endpoint")


def _diagnostics_roots(store: Store, extra_allowed_roots) -> list[Path]:
    """Return the confinement boundary for the read-only diagnostics.

    SEC-2/SEC-3: the store's own data directory is always included, and an
    operator who wants the effective-resolution view of a real project tree
    adds it explicitly (``extra_allowed_roots``), so no request can widen the
    boundary on its own.
    """
    roots = [Path(store.data_dir)]
    for extra in extra_allowed_roots or ():
        roots.append(Path(extra).expanduser())
    return [Path(root).resolve() for root in roots]


class _StoreBoundHTTPServer(ThreadingHTTPServer):
    """A threading server that binds its own Store for each request thread.

    SCOPE-10: ``scopes`` resolves the ``global`` scope through an injectable
    Store.  When that injection was a process-wide module global the last
    ``WebAppServer`` constructed won for *every* path that went through it, so
    one server's REST responses (and its agent-scope snapshots) were served from
    another server's data dir.  Binding at the start of the request thread makes
    the association per-server and per-request regardless of how many servers
    share the process.
    """

    store = None  # type: ignore[assignment]

    def process_request_thread(self, request, client_address):
        if self.store is not None:  # type: ignore[attr-defined]
            set_active_store(self.store)  # type: ignore[attr-defined]
        super().process_request_thread(request, client_address)


def _bind_server(normalized_host: str, port: int, requested_host: str):
    """Bind the *validated* host, translating a socket failure cleanly.

    Binding ``host`` while the policy checked ``normalized_host`` meant a
    trailing space or a bare IPv6 literal passed the loopback check and then
    raised the interpreter's own ``gaierror`` out of the constructor
    (docs/24 §D3-12).
    """
    try:
        return _StoreBoundHTTPServer((normalized_host, port), WebAppHandler)
    except OSError as exc:
        raise StoreError(
            f"cannot bind the web UI to {requested_host!r}: {exc.strerror or exc}"
        ) from exc


class WebAppServer:
    def __init__(self, store: Store, host: str = "127.0.0.1", port: int = 0,
                 extra_allowed_roots: list[str | Path] | None = None):
        normalized_host = host.strip().lower()
        is_localhost_name = normalized_host == "localhost"
        try:
            is_loopback = ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            is_loopback = False
        if not (is_localhost_name or is_loopback):
            raise StoreError("web UI host must be loopback (127.0.0.1, ::1, or localhost)")
        # Bind the *validated* host. Binding `host` while checking
        # `normalized_host` meant a trailing space or a bare IPv6 literal
        # passed the loopback policy and then raised the interpreter's own
        # gaierror out of the constructor (docs/24 §D3-12).
        self.httpd = _bind_server(normalized_host, port, host)
        self.httpd.store = store  # type: ignore[attr-defined]
        self.host = host
        self.port = self.httpd.server_address[1]
        self.httpd.diagnostics_roots = _diagnostics_roots(store, extra_allowed_roots)  # type: ignore[attr-defined]
        bound_host = self.httpd.server_address[0]
        hostnames = {host, bound_host}
        if normalized_host == "localhost":
            hostnames.update({"127.0.0.1", "::1"})
        self.httpd.allowed_hosts = {
            f"{name}:{self.port}" if ":" not in name else f"[{name}]:{self.port}"
            for name in hostnames
        }  # type: ignore[attr-defined]
        self.httpd.allowed_origins = {
            f"http://{value}" for value in self.httpd.allowed_hosts
        }  # type: ignore[attr-defined]
        # Also bind in the *constructing* thread so direct (non-HTTP) callers in
        # that thread see this server's store; request threads rebind their own
        # copy above, which is what stops two servers from crossing over.
        set_active_store(store)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _open_browser(url: str, *, which=shutil.which) -> None:
    _launch_browser(trusted_executable("xdg-open", which=which), url)


def _launch_browser(executable: str | None, url: str) -> None:
    """Launch an already trusted opener, or leave the URL for the operator."""
    if not executable:
        return
    try:
        subprocess.Popen(
            [executable, url],  # nosec B603 - executable is owner/permission validated above.
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        _diagnose("browser opener failed", exc)


def run(
    store: Store | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> int:
    if store is None:
        store = Store()
    server = WebAppServer(store, host, port)
    url = server.url
    print(f"Skills Manager web UI running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, _open_browser, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(run())

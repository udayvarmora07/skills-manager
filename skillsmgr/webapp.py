"""Local web UI backend for skills-mgr (stdlib only).

Serves a single-page frontend (``webui/``) plus a JSON REST API over the
Store public API. Binds to 127.0.0.1 only — this is local desktop
software, never a public service.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .store import Store, StoreError, SkillNotFound
from .diagnostics import diagnose as _diagnose
# ``RequestError`` is re-exported deliberately: callers imported it from this
# module before the web_security extraction, and tests/test_compatibility.py
# pins that import path.  It is not dead code (BUG-15).
from .web_security import RequestError, validate_request  # noqa: F401
from .web_serialization import json_bytes, parse_json_object
from .web_upload import MAX_UPLOAD_PARTS, parse_multipart, upload_folder

_WEBUI_DIR = Path(__file__).resolve().parent / "webui"
_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

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
    from .insights import registry_bridge_plan

    raw_agents = data.get("agents")
    raw_skills = data.get("skills")
    agents = [raw_agents] if isinstance(raw_agents, str) else raw_agents
    skills = [raw_skills] if isinstance(raw_skills, str) else raw_skills
    description = data.get("description")
    payload["registry"] = registry_bridge_plan(
        source,
        runner=runner,
        scope=str(data.get("scope", "global") or "global"),
        agents=agents,
        skills=skills,
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


def _registry_fetch_result(store: Store, data: dict, allow_stale: bool) -> dict:
    """Run the registry review or the separate reviewed commit transaction."""
    from .cli_handlers import _commit_registry_review, _prepare_registry_skill

    review_id = data.get("review_id")
    if review_id is not None:
        if not isinstance(review_id, str) or not review_id.strip():
            raise StoreError("review_id must be a non-empty string")
        if data.get("trust_confirmed") is not True:
            raise StoreError("registry commit requires trust_confirmed after reviewing the fetched snapshot")
        return _commit_registry_review(store, review_id.strip())
    if data.get("trust_confirmed") is True:
        raise StoreError("fetch and trust confirmation are separate: fetch first, then commit with review_id and trust_confirmed")
    source = data.get("source")
    if not isinstance(source, str) or not source.strip():
        raise StoreError("fetch requires a registry skill id in source")
    scope = data.get("scope", "global")
    if not isinstance(scope, str) or (scope.strip() or "global") != "global":
        raise StoreError("registry fetch currently targets the global manager store only")
    expected_hash = data.get("registry_hash")
    if expected_hash is not None and not isinstance(expected_hash, str):
        raise StoreError("registry_hash must be a string")
    return _prepare_registry_skill(
        store, source.strip(), expected_hash=expected_hash, allow_stale=allow_stale
    )


def _registry_install_result(store: Store, data: dict) -> dict | None:
    """Handle registry operations carried by the existing install route."""
    operation = _registry_operation_kind(data)
    if operation is None:
        return None
    if data.get("run") or data.get("preview"):
        raise StoreError("registry operations cannot be combined with run or preview")
    from .registry import RegistryClient

    client = RegistryClient(store.data_dir)
    allow_stale = bool(data.get("allow_stale"))
    if operation == "fetch":
        return _registry_fetch_result(store, data, allow_stale)
    return _registry_read_result(client, operation, data, allow_stale)


def _validate_payload(store: Store, data: dict, name: str, skill_dir: Path,
                      payload: dict) -> dict:
    """Add the advisory eval harness block to ``/api/validate`` on request.

    Recording is opt-in (``runs``) and only ever writes inside the store's
    ``evals/`` workspace, so the default request keeps its read-only contract.
    """
    if not (data.get("evals") or data.get("runs")):
        return payload
    from . import evals as evals_mod

    report = evals_mod.load_cases(skill_dir)
    workspace = evals_mod.workspace_for(store.data_dir, name)
    report["workspace"] = str(workspace)
    if data.get("runs"):
        blocking = [issue for issue in report["issues"] if issue["level"] == "error"]
        if blocking:
            raise StoreError(f"cannot record eval runs for '{name}': {blocking[0]['message']}")
        if not report["cases"]:
            raise StoreError(f"cannot record eval runs for '{name}': no eval cases found")
        iteration = data.get("iteration", 1)
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
            raise StoreError("iteration must be a positive integer")
        report["recording"] = evals_mod.record_runs(
            workspace, iteration, report["cases"], data.get("runs")
        )
    payload["evals"] = report
    return payload


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
    scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
    report = store.doctor()
    if scope == "all":
        # BUG-8: this swallow made `/api/doctor?scope=all` return a payload
        # *without* scopes/duplicates while still reporting success, so a client
        # could not tell "no duplicates" from "the duplicate scan crashed".
        try:
            from .scopes import find_duplicates as _dupes
            from .scopes import list_scopes as _lscopes

            report["scopes"] = _lscopes()
            report["duplicates"] = _dupes()
        except Exception as exc:
            _diagnose("doctor scope=all enrichment failed", exc)
            report["scopes"] = []
            report["duplicates"] = []
            report.setdefault("degraded", []).append(
                {
                    "section": "scopes/duplicates",
                    "reason": f"the scope and duplicate scan failed: {exc}",
                }
            )
    consumer = (qs.get("explain", [""])[0] or "").strip()
    if consumer:
        from . import effective

        report["explain"] = effective.explain(
            consumer,
            (qs.get("project", [""])[0] or "").strip() or None,
            skill=(qs.get("skill", [""])[0] or "").strip() or None,
            allowed_root=diagnostics_roots,
        )
    return report


def _skill_text(skill_dir: Path) -> str:
    """Return a skill's document text, or ``""`` when there is none to read."""
    for candidate in (skill_dir / "SKILL.md", skill_dir / "SKILL.md.disabled"):
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
    return ""


def _apply_token_estimate(record: dict, tok) -> None:
    """Copy one token estimate onto a REST record."""
    record["tokens"] = tok["tokens"]
    record["tokens_method"] = tok["method"]
    record["tokens_pct"] = tok["pct_window"]
    record["chars"] = tok["chars"]


def _enrich_rows_with_tokens(store: Store, rows: list[dict], label: str) -> None:
    """Add token estimates to list rows, reporting a failure instead of hiding it.

    BUG-8: four copies of this loop swallowed every failure with
    ``except Exception: pass``, so a crash left a ``200`` payload silently
    missing documented keys (which is what produced BUG-7).  A failure is now
    diagnosed and marked on the rows it affected.
    """
    try:
        physical_root = str(store.skills_dir.resolve())
        from .tokens import estimate as _est

        for row in rows:
            row.setdefault("physical_root", physical_root)
            if row.get("path"):
                try:
                    row.setdefault("physical_path", str(Path(row["path"]).resolve()))
                except OSError:
                    row.setdefault("physical_path", str(row["path"]))
            _apply_token_estimate(row, _est(_skill_text(store.skills_dir / row["name"])))
    except Exception as exc:
        _diagnose(f"{label} token enrichment failed", exc)
        for row in rows:
            row.setdefault("tokens", 0)
            row.setdefault("tokens_method", "unavailable")
            row.setdefault("tokens_pct", 0)
            row.setdefault("chars", 0)


def _enrich_rows_with_catalog(store: Store, rows: list[dict]) -> None:
    """Attach manager-owned tags without changing skill or index authority."""
    from .catalog import enrich_rows

    enrich_rows(rows, data_dir=store.data_dir)


def _batch_target_inputs(item: object) -> tuple[str, str, str]:
    if not isinstance(item, dict):
        raise StoreError("each batch target must be an object")
    name = item.get("name")
    scope = item.get("scope")
    if not isinstance(name, str) or not name.strip() or not isinstance(scope, str) or not scope.strip():
        raise StoreError("each batch target needs a name and scope")
    return name.strip(), scope.strip(), str(item.get("physical_path") or item.get("path") or "")


def _batch_target_candidates(
    name: str, scope: str, physical: str, records: list[dict]
) -> list[dict]:
    candidates = [row for row in records if row.get("name") == name and row.get("scope") == scope]
    if physical:
        candidates = [
            row for row in candidates
            if str(row.get("physical_path") or row.get("path") or "") == physical
        ]
    return candidates


def _resolve_batch_target(item: object, records: list[dict], seen: set[tuple[str, str, str]]) -> dict:
    name, scope, physical = _batch_target_inputs(item)
    candidates = _batch_target_candidates(name, scope, physical, records)
    if not candidates:
        raise StoreError(f"batch target is no longer present: {scope}/{name}")
    if len(candidates) > 1:
        raise StoreError(f"batch target is ambiguous; include its physical_path: {scope}/{name}")
    row = candidates[0]
    path = str(row.get("physical_path") or row.get("path") or "")
    key = (scope, name, path)
    if key in seen:
        raise StoreError(f"duplicate batch target: {scope}/{name}")
    seen.add(key)
    return {
        "name": name,
        "scope": scope,
        "scope_label": row.get("scope_label", scope),
        "path": row.get("path"),
        "physical_path": row.get("physical_path") or row.get("path"),
        "disabled": bool(row.get("disabled")),
        "instance_state": row.get("instance_state", "unresolved"),
    }


def _batch_targets(data: dict) -> list[dict]:
    """Validate and resolve an exact physical target selection."""
    raw = data.get("targets")
    if not isinstance(raw, list) or not raw or len(raw) > 500:
        raise StoreError("targets must be a non-empty list of at most 500 items")
    from .scopes import list_all as _list_all

    records = _list_all()
    seen: set[tuple[str, str, str]] = set()
    return [_resolve_batch_target(item, records, seen) for item in raw]


def _batch_plan(operation: str, targets: list[dict], data: dict) -> dict:
    from .catalog import plan_hash

    options = {
        "force": bool(data.get("force")),
        "to_scopes": sorted({str(scope) for scope in (data.get("to_scopes") or [])}),
    }
    return {
        "operation": operation,
        "targets": targets,
        "target_count": len(targets),
        "atomic": False,
        "partial_failure": True,
        "recovery": "remove creates per-item trash snapshots; other actions report each item",
        "options": options,
        "plan_id": plan_hash(operation, targets, options),
    }


def _validated_skill_fields(data: dict) -> dict:
    """Select skill fields while enforcing the Store/scopes string contract."""
    fields = {}
    for field in _SKILL_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field == "allowed_tools":
            if not isinstance(value, str):
                raise StoreError("allowed_tools must be a string")
        elif not isinstance(value, str):
            raise StoreError(f"{field} must be a string")
        if value != "":
            fields[field] = value
    return fields


def _head_safe_body(command: str, body: bytes) -> bytes:
    """Return the bytes to write for *command*: none at all for HEAD (BUG-9)."""
    return b"" if command == "HEAD" else body


#: BUG-9: the verbs this server routes, advertised on a 405.
_ALLOWED_METHODS = "GET, HEAD, POST, PATCH, PUT, DELETE"
_METHOD_NOT_ALLOWED_BODY = b'{"error": "method not allowed"}'

MAX_BODY_BYTES = 25 * 1024 * 1024
MAX_UPLOAD_PARTS = 200
MAX_QUERY_LEN = 200
MAX_HISTORY_LIMIT = 200


# Compatibility aliases for callers/tests that imported these implementation
# helpers before the internal extraction.  They are intentionally private and
# keep the old call shape, including the ignored serialization status argument.
def _json_bytes(obj, status: int = 200) -> bytes:
    return json_bytes(obj)


def _parse_multipart(raw: bytes, boundary: str) -> list[dict]:
    return parse_multipart(raw, boundary)


class WebAppHandler(BaseHTTPRequestHandler):
    server_version = "skillsmgr-webui"

    @property
    def store(self) -> Store:
        return self.server.store  # type: ignore[attr-defined]

    # -- plumbing ---------------------------------------------------------

    def log_message(self, fmt, *args):  # quiet by default
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        # A HEAD response carries the same headers as the equivalent GET but no
        # body (BUG-9); Content-Length still describes the entity that a GET
        # would have returned.
        self._write_body(_head_safe_body(self.command, body))

    def _write_body(self, body: bytes) -> None:
        """Write a response without treating a disconnected client as a bug."""
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browsers and smoke clients can leave while a response is being
            # produced.  The request is already over from the client's point
            # of view; there is no useful error response left to send.
            return

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

    def _send_json(self, obj, status: int = 200) -> None:
        self._send(status, _json_bytes(obj))

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _drain_body(self, length: int) -> None:
        """Read and discard an over-limit body before sending its error."""
        remaining = length
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass

    def _read_body(self, limit: int = MAX_BODY_BYTES) -> bytes:
        raw_length = self.headers.get("Content-Length") or "0"
        try:
            length = int(str(raw_length).strip())
        except ValueError:
            raise StoreError("invalid Content-Length")
        if length < 0:
            raise StoreError("invalid Content-Length")
        if length > limit:
            self._drain_body(length)
            raise RequestError(413, "request body too large")
        return self.rfile.read(length) if length else b""

    def _body_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        return parse_json_object(raw, self.headers.get("Content-Type", ""))

    @staticmethod
    def _unquote(name: str) -> str:
        return unquote(name)

    # -- routing ----------------------------------------------------------

    def do_GET(self):
        try:
            self._validate_request()
            self._route_get()
        except Exception as exc:
            self._handle_exception(exc)

    def do_POST(self):
        try:
            self._validate_request()
            self._route_post()
        except Exception as exc:
            self._handle_exception(exc)

    def do_PATCH(self):
        try:
            self._validate_request()
            self._route_patch()
        except Exception as exc:
            self._handle_exception(exc)

    def do_DELETE(self):
        try:
            self._validate_request()
            self._route_delete()
        except Exception as exc:
            self._handle_exception(exc)

    def do_PUT(self):
        try:
            self._validate_request()
            self._route_put()
        except Exception as exc:
            self._handle_exception(exc)

    def do_HEAD(self):
        """Answer HEAD like the equivalent GET, headers only (BUG-9).

        The stdlib's default handler answered HEAD/OPTIONS/TRACE with a 501 HTML
        page that carried **no** security headers at all, so those verbs
        bypassed the whole response policy.  HEAD now goes through the read
        router with the body suppressed by ``_send``.
        """
        try:
            self._validate_request()
            self._route_get()
        except Exception as exc:
            self._handle_exception(exc)

    def do_OPTIONS(self):
        self._unsupported_method()

    def do_TRACE(self):
        self._unsupported_method()

    def _unsupported_method(self) -> None:
        """Refuse an unrouted verb with the standard policy and headers."""
        try:
            self._validate_request()
            self.send_response(405)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Allow", _ALLOWED_METHODS)
            self.send_header("Content-Length", str(len(_METHOD_NOT_ALLOWED_BODY)))
            self.send_header("Cache-Control", "no-store")
            self._send_security_headers()
            self.end_headers()
            if self.command != "HEAD":
                self._write_body(_METHOD_NOT_ALLOWED_BODY)
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        if isinstance(exc, SkillNotFound):
            self._send_error(404, str(exc))
        elif isinstance(exc, StoreError):
            self._send_error(getattr(exc, "status", 400), str(exc))
        elif isinstance(exc, ValueError):
            self._send_error(400, str(exc))
        else:
            print(f"webui internal error: {exc!r}", file=sys.stderr)
            self._send_error(500, "internal error")

    def _expected_origin(self) -> str:
        host = self.server.server_address[0]  # type: ignore[attr-defined]
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.server.server_port}"  # type: ignore[attr-defined]

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

    def _serve_static(self) -> bool:
        parts = self._parts()
        rel = parts[0] if parts else "index.html"
        if rel == "api":
            return False
        if rel == "" or rel == "index.html":
            rel = "index.html"
        elif rel == "static" and len(parts) >= 2:
            rel = "static/" + "/".join(parts[1:])
        candidate = (_WEBUI_DIR / rel).resolve()
        try:
            inside = candidate.is_relative_to(_WEBUI_DIR)
        except AttributeError:
            inside = str(candidate).startswith(str(_WEBUI_DIR) + os.sep)
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

    def _route_get(self):
        parts = self._parts()
        if self._serve_static():
            return
        qs = parse_qs(urlparse(self.path).query)
        if parts == ["api", "scopes"]:
            from .scopes import list_scopes as _list_scopes

            self._send_json(_list_scopes())
            return
        if parts == ["api", "catalog"]:
            from .catalog import load_catalog

            self._send_json(load_catalog(self.store.data_dir))
            return
        if parts == ["api", "workspaces"]:
            from .adapters import workspaces_payload

            project = (qs.get("project", [""])[0] or "").strip() or None
            roots = getattr(self.server, "diagnostics_roots", None) or [self.store.data_dir]
            self._send_json(workspaces_payload(project, roots))
            return
        if len(parts) == 5 and parts[:3] == ["api", "catalog", "profiles"] and parts[4] == "preview":
            from .catalog import load_catalog, profile_preview
            from .scopes import list_all as _list_all

            profile_name = parts[3]
            profile = load_catalog(self.store.data_dir)["profiles"].get(profile_name)
            if profile is None:
                raise SkillNotFound(f"profile '{profile_name}' not found")
            self._send_json({"name": profile_name, **profile_preview(profile, _list_all())})
            return
        if parts == ["api", "skills"]:
            scope = (qs.get("scope", [""])[0] or "").strip()
            q = (qs.get("q", [""])[0] or "").strip()
            if scope == "all":
                if q:
                    from .scopes import search_all as _search_all

                    rows = _search_all(q, scope_id="all", store=self.store)
                else:
                    from .scopes import list_all as _list_all

                    rows = _list_all()
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
                return
            if scope and scope != "global":
                from .scopes import scan_scope as _scan_scope, search_all as _search_all

                if q:
                    rows = _search_all(q, scope_id=scope)
                else:
                    rows = _scan_scope(scope)
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
                return
            # scope == "" or "global": use the scope adapter so wildcard
            # validation and body-aware ranking share one StoreError seam.
            if q:
                from .scopes import search_all as _search_all

                rows = _search_all(q, scope_id="global", store=self.store)
                for r in rows:
                    r.setdefault("scope", "global")
                    r.setdefault("scope_label", "Global")
                # Add token enrichment from actual files
                _enrich_rows_with_tokens(self.store, rows, "all-scope list")
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
            else:
                rows = self.store.list()
                for r in rows:
                    r.setdefault("scope", "global")
                    r.setdefault("scope_label", "Global")
                # Token enrichment for list rows
                _enrich_rows_with_tokens(self.store, rows, "global list")
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
            return
        if parts == ["api", "search"]:
            scope = (qs.get("scope", [""])[0] or "global").strip() or "global"
            q = qs.get("q", [""])[0]
            if len(q) > MAX_QUERY_LEN:
                self._send_error(400, "search query too long")
                return
            if scope in ("all", ""):
                if scope == "all":
                    from .scopes import search_all as _search_all

                    rows = _search_all(q, scope_id="all", store=self.store)
                else:
                    rows = self.store.search(q)
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
            elif scope == "global":
                from .scopes import search_all as _search_all

                rows = _search_all(q, scope_id="global", store=self.store)
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
            else:
                from .scopes import search_all as _search_all

                rows = _search_all(q, scope_id=scope)
                _enrich_rows_with_catalog(self.store, rows)
                self._send_json(rows)
            return
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "raw":
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                from .scopes import get_raw as _get_raw

                raw = _get_raw(scope, parts[2])
                self._send(200, raw.encode("utf-8"), "text/plain; charset=utf-8")
                return
            # Resolve through Store.get() first so the decoded path segment is
            # validated before it can be used for a filesystem read.
            record = self.store.get(parts[2])
            skill_dir = Path(record["path"]) if record.get("path") else self.store.skills_dir / parts[2]
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                skill_file = skill_dir / "SKILL.md.disabled"
            if not skill_file.is_file():
                self._send_error(404, f"skill '{parts[2]}' has no SKILL.md")
                return
            raw = skill_file.read_text(encoding="utf-8")
            self._send(200, raw.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                from .scopes import get_skill as _get_skill

                record = _get_skill(scope, parts[2])
                _enrich_rows_with_catalog(self.store, [record])
                self._send_json(record)
                return
            # Use injected store for correct data_dir in tests, with token enrichment
            rec = self.store.get(parts[2])
            rec.setdefault("scope", "global")
            rec.setdefault("scope_label", "Global")
            try:
                from .tokens import estimate as _estD

                tok = _estD(_skill_text(self.store.skills_dir / parts[2]))
                _apply_token_estimate(rec, tok)
                rec["lines"] = tok["lines"]
                rec["body_tokens"] = _estD(rec.get("body") or "")["tokens"]
                rec["frontmatter_tokens"] = max(0, tok["tokens"] - rec["body_tokens"])
            except Exception as exc:
                _diagnose(f"detail token enrichment failed for {parts[2]!r}", exc)
                rec.setdefault("tokens", 0)
                rec.setdefault("tokens_method", "unavailable")
            _enrich_rows_with_catalog(self.store, [rec])
            self._send_json(rec)
            return
        if parts == ["api", "trash"]:
            self._send_json(self.store.trash_list())
        elif parts == ["api", "templates"]:
            from .templates import list_templates

            self._send_json({"templates": list_templates(self.store.templates_dir)})
        elif parts == ["api", "history"]:
            name = qs.get("name", [None])[0]
            try:
                limit = int(qs.get("limit", ["50"])[0])
            except ValueError:
                limit = 50
            limit = max(1, min(limit, MAX_HISTORY_LIMIT))
            if qs.get("snapshots", ["0"])[0] in ("1", "true", "yes") and name:
                scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
                if scope == "global":
                    from .store import list_snapshots as _list_snapshots

                    snapshots = _list_snapshots(self.store.data_dir, "global", name)
                else:
                    from .scopes import list_snapshots_for as _list_snapshots_for

                    snapshots = _list_snapshots_for(scope, name)
                self._send_json({"name": name, "scope": scope, "snapshots": snapshots})
                return
            self._send_json(self.store.history(name=name, limit=limit))
        elif parts == ["api", "stats"]:
            st = self.store.stats()
            win_qs = (qs.get("window", ["claude"])[0] or "claude").strip()
            try:
                from .scopes import list_scopes as _list_scopes
                from .tokens import WINDOWS as _WINDOWS

                from .scopes import list_all as _list_all

                records = _list_all()
                scopes = _list_scopes(records=records)
                st["scopes"] = scopes
                st["all_total"] = sum(s["count"] for s in scopes)
                st["all_tokens"] = sum(s.get("tokens", 0) for s in scopes)
                st["all_avg_tokens"] = (st["all_tokens"] // st["all_total"]) if st["all_total"] else 0
                # Token budget vs selected window.
                win = _WINDOWS.get(win_qs, _WINDOWS.get("claude", 200_000))
                st["window"] = win_qs
                st["window_tokens"] = win
                st["all_pct_window"] = round(st["all_tokens"] / win * 100, 1) if win else 0
                # Top 5 largest across all scopes.
                try:
                    st["largest"] = sorted(records, key=lambda r: r.get("tokens", 0), reverse=True)[:5]
                    st["largest"] = [{"name": r["name"], "scope": r.get("scope"), "tokens": r.get("tokens", 0)} for r in st["largest"]]
                except Exception as exc:
                    _diagnose("stats largest-skills scan failed", exc)
                    st["largest"] = []
                    st.setdefault("degraded", []).append("largest")
                # Whether exact counting is available.
                try:
                    from .tokens import _HAS_TIKTOKEN as _ht

                    st["has_tiktoken"] = bool(_ht)
                except Exception as exc:
                    _diagnose("stats tokenizer probe failed", exc)
                    st["has_tiktoken"] = False
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
        elif parts == ["api", "tokens"]:
            win = (qs.get("window", ["claude"])[0] or "claude").strip()
            name = (qs.get("name", [""])[0] or "").strip()
            scope = (qs.get("scope", ["all"])[0] or "all").strip()
            text = (qs.get("text", [""])[0] or "")
            if text:
                from .tokens import estimate as _est

                self._send_json(_est(text, window=win))
                return
            if name:
                if scope and scope not in ("all", ""):
                    from .scopes import get_skill as _get_skill

                    rec = _get_skill(scope, name)
                else:
                    # Find first match across all scopes.
                    from .scopes import list_all as _list_all

                    rec = next((r for r in _list_all() if r["name"] == name), None)
                    if rec is None:
                        raise SkillNotFound(f"skill '{name}' not found")
                    # Enrich with full record for body.
                    try:
                        from .scopes import get_skill as _gs

                        rec = _gs(rec.get("scope", "global"), name)
                    except Exception as exc:
                        # The listing record is still usable; say why it is thin
                        # rather than silently returning a partial record.
                        _diagnose(f"tokens detail enrichment failed for {name!r}", exc)
                from .tokens import estimate as _est2

                raw = ""
                p = Path(rec.get("path", "")) if rec.get("path") else None
                if p and p.is_dir():
                    for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                        if cand.is_file():
                            raw = cand.read_text(encoding="utf-8")
                            break
                if not raw and rec.get("body"):
                    raw = rec.get("body", "")
                self._send_json(_est2(raw or "", window=win))
                return
            # No name/text: aggregate over scope.
            if scope in ("all", "", None):
                from .scopes import list_all as _list_all
                from .tokens import aggregate as _agg

                agg = _agg(_list_all())
                agg["window"] = win
                from .tokens import WINDOWS as _WW

                wtok = _WW.get(win, _WW.get("claude", 200_000))
                agg["window_tokens"] = wtok
                agg["pct_window"] = round(agg["total_tokens"] / wtok * 100, 1) if wtok else 0
                self._send_json(agg)
                return
            from .scopes import scan_scope as _scan_scope
            from .tokens import aggregate as _agg2

            agg = _agg2(_scan_scope(scope))
            agg["window"] = win
            from .tokens import WINDOWS as _WW2

            wtok = _WW2.get(win, _WW2.get("claude", 200_000))
            agg["window_tokens"] = wtok
            agg["pct_window"] = round(agg["total_tokens"] / wtok * 100, 1) if wtok else 0
            self._send_json(agg)
            return
        elif parts == ["api", "doctor"]:
            self._send_json(
                _doctor_payload(
                    self.store, qs, getattr(self.server, "diagnostics_roots", None) or [self.store.data_dir]
                )
            )
        elif parts == ["api", "export"]:
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                self._send_error(400, "export is only available for the global scope")
                return
            archive = self.store.export(full=qs.get("full", ["0"])[0] in ("1", "true", "yes"))
            body = archive.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Disposition", f'attachment; filename="{archive.name}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._send_security_headers()
            self.end_headers()
            self._write_body(body)
        else:
            self._send_error(404, "unknown endpoint")

    # -- POST routes ------------------------------------------------------

    def _execute_batch_post(self) -> bool:
        data = self._body_json()
        operation = data.get("operation")
        if operation not in {"enable", "disable", "remove", "sync"}:
            raise StoreError("batch operation must be enable, disable, remove, or sync")
        targets = _batch_targets(data)
        plan = _batch_plan(operation, targets, data)
        if data.get("plan_id") != plan["plan_id"]:
            raise StoreError("batch preview is stale; review the current targets again")
        if operation == "sync" and not plan["options"]["to_scopes"]:
            raise StoreError("sync batch plans require at least one target scope")
        results: list[dict] = []
        from .scopes import remove_skill as _remove_skill, sync_skill as _sync_skill, toggle_skill as _toggle_skill

        for target in targets:
            item = {"name": target["name"], "scope": target["scope"], "status": "ok"}
            try:
                if operation in {"enable", "disable"}:
                    desired = operation == "enable"
                    if target["disabled"] == (not desired):
                        item["result"] = "already-set"
                    else:
                        item.update(_toggle_skill(target["scope"], target["name"], enable=desired))
                elif operation == "remove":
                    item.update(_remove_skill(target["scope"], target["name"], purge=False))
                else:
                    item.update(_sync_skill(
                        target["name"], target["scope"], plan["options"]["to_scopes"],
                        force=bool(plan["options"]["force"]),
                    ))
            except (StoreError, OSError, ValueError) as exc:
                item["status"] = "failed"
                item["error"] = str(exc)
            results.append(item)
        failures = [item for item in results if item["status"] == "failed"]
        self._send_json({
            "operation": operation,
            "plan_id": plan["plan_id"],
            "target_count": len(targets),
            "results": results,
            "ok": not failures,
            "partial": bool(failures) and len(failures) < len(results),
        })
        return True

    def _route_batch_post(self, parts: list[str]) -> bool:
        if parts == ["api", "batch", "preview"]:
            data = self._body_json()
            operation = data.get("operation")
            if operation not in {"enable", "disable", "remove", "sync"}:
                raise StoreError("batch operation must be enable, disable, remove, or sync")
            if operation == "sync" and not isinstance(data.get("to_scopes"), list):
                raise StoreError("sync batch plans require a to_scopes list")
            targets = _batch_targets(data)
            self._send_json(_batch_plan(operation, targets, data))
            return True
        if parts == ["api", "batch", "execute"]:
            return self._execute_batch_post()
        return False

    def _route_catalog_post(self, parts: list[str]) -> bool:
        if parts == ["api", "catalog", "tags"]:
            data = self._body_json()
            names = data.get("names")
            values = data.get("tags")
            if not isinstance(names, list) or not isinstance(values, list):
                raise StoreError("tag updates require names and tags lists")
            from .catalog import update_tags

            self._send_json(update_tags(self.store.data_dir, names, data.get("operation", "add"), values))
            return True
        if parts != ["api", "catalog", "profiles"]:
            return False
        data = self._body_json()
        name = data.pop("name", None)
        if not isinstance(name, str):
            raise StoreError("profile name must be a string")
        from .catalog import save_profile

        self._send_json(save_profile(self.store.data_dir, name, data))
        return True

    def _route_new_post(self, parts: list[str]) -> bool:
        if parts[:2] == ["api", "batch"]:
            return self._route_batch_post(parts)
        if parts[:2] == ["api", "catalog"]:
            return self._route_catalog_post(parts)
        return False

    def _route_post(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query)
        if self._route_new_post(parts):
            return
        if parts == ["api", "sync"]:
            data = self._body_json()
            raw_name = data.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise StoreError("name must be a string")
            name = raw_name.strip()
            raw_from_scope = data.get("from_scope") or "global"
            if not isinstance(raw_from_scope, str):
                raise StoreError("from_scope must be a string")
            from_scope = raw_from_scope.strip() or "global"
            to_scopes = data.get("to_scopes")
            force = bool(data.get("force"))
            if not name:
                raise StoreError("name is required for sync")
            from .scopes import sync_skill as _sync_skill

            self._send_json(_sync_skill(name, from_scope, to_scopes, force=force))
            return
        if parts == ["api", "install"]:
            data = self._body_json()
            result = _registry_install_result(self.store, data)
            if result is not None:
                self._send_json(result)
                return
            raw_source = data.get("source")
            if not isinstance(raw_source, str):
                raise StoreError("source must be a string")
            source = raw_source.strip()
            if not source:
                raise StoreError("source is required (e.g. vercel-labs/agent-skills)")
            from .cli_handlers import validated_install_source, validated_install_value

            source = validated_install_source(source)
            agents = data.get("agents")
            skills_filter = data.get("skills")
            raw_scope = data.get("scope", "global")
            if not isinstance(raw_scope, str):
                raise StoreError("scope must be a string")
            scope = raw_scope.strip() or "global"
            copy_mode = bool(data.get("copy"))
            list_only = bool(data.get("list_only"))
            if agents is not None and not isinstance(agents, list):
                agents = [agents] if isinstance(agents, str) else None
            if skills_filter is not None and not isinstance(skills_filter, list):
                skills_filter = [skills_filter] if isinstance(skills_filter, str) else None
            raw_runner = data.get("runner", "npx")
            if not isinstance(raw_runner, str):
                raise StoreError("runner must be a string")
            runner = raw_runner.strip() or "npx"
            allowed_runners = {"npx", "pnpm", "yarn", "bunx", "bun"}
            if runner == "uvx":
                raise StoreError("uvx does not apply to the npm 'skills' package; use npx/pnpm dlx/yarn dlx/bunx. For Python tools use pipx/uvx with a PyPI package.")
            if runner not in allowed_runners:
                raise StoreError(f"unsupported runner {runner!r}; use npx, pnpm, yarn, or bunx")
            if runner == "npx":
                cmd_parts = ["npx", "skills", "add", source]
            elif runner == "pnpm":
                cmd_parts = ["pnpm", "dlx", "skills", "add", source]
            elif runner == "yarn":
                cmd_parts = ["yarn", "dlx", "skills", "add", source]
            elif runner in ("bunx", "bun"):
                cmd_parts = ["bunx", "skills", "add", source]
            else:
                cmd_parts = ["npx", "skills", "add", source]
            if scope == "global":
                cmd_parts.append("-g")
            if agents:
                for a in agents:
                    a = validated_install_value("agent", str(a))
                    cmd_parts.extend(["-a", a])
            if skills_filter:
                for s in skills_filter:
                    s = validated_install_value("skill", str(s))
                    cmd_parts.extend(["-s", s])
            if copy_mode:
                cmd_parts.append("--copy")
            if list_only:
                cmd_parts.append("-l")
            cmd_str = " ".join(cmd_parts)
            if not data.get("run"):
                self._send_json(_install_preview_payload(self.store, data, source, cmd_str, runner))
                return
            try:
                proc = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=120)
                self._send_json({
                    "command": cmd_str,
                    "runner": runner,
                    "source": source,
                    "executed": True,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[-8000:],
                    "stderr": proc.stderr[-8000:],
                })
            except subprocess.TimeoutExpired as exc:
                self._send_json({"command": cmd_str, "error": f"timed out after 120s: {exc}", "executed": True}, 500)
            except FileNotFoundError as exc:
                raise StoreError(f"runner not found: {exc}")
            return
        if parts == ["api", "skills"]:
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            data = self._body_json()
            name = data.pop("name", None)
            description = data.pop("description", None)
            if not isinstance(name, str) or not name.strip():
                raise StoreError("name must be a non-empty string")
            if not isinstance(description, str) or not description.strip():
                raise StoreError("description must be a non-empty string")
            fields = _validated_skill_fields(data)
            if scope != "global":
                from .scopes import create_skill as _create_skill

                self._send_json(_create_skill(scope, name, description, **fields), 201)
                return
            self._send_json(self.store.create(name, description, **fields), 201)
        elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] in ("disable", "enable"):
            name = parts[2]
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                from .scopes import toggle_skill as _toggle_skill

                self._send_json(_toggle_skill(scope, name, enable=(parts[3] == "enable")))
                return
            action = getattr(self.store, parts[3])
            action(name)
            self._send_json({"name": name, parts[3]: True})
        elif parts[:2] == ["api", "trash"]:
            if len(parts) == 3 and parts[2] == "purge":
                self._send_json(self.store.purge_trash())
            elif len(parts) == 3:
                snapshot = qs.get("snapshot", [None])[0]
                if snapshot:
                    scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
                    if scope == "global":
                        self._send_json(self.store.restore(parts[2], snapshot=snapshot))
                    else:
                        from .scopes import restore_snapshot as _restore_snapshot

                        self._send_json(_restore_snapshot(scope, parts[2], snapshot))
                else:
                    self._send_json(self.store.restore(parts[2]))
            else:
                self._send_error(404, "unknown endpoint")
        elif parts == ["api", "templates"]:
            data = self._body_json()
            name = data.get("name")
            if not isinstance(name, str) or not name.strip():
                raise StoreError("template name must be a non-empty string")
            body = data.get("body")
            if body is not None and not isinstance(body, str):
                raise StoreError("template body must be a string")
            from .templates import create_template

            try:
                path = create_template(self.store.templates_dir, name, data.get("body") or None)
            except FileExistsError as exc:
                raise StoreError(str(exc)) from exc
            except ValueError as exc:
                raise StoreError(str(exc)) from exc
            self._send_json({"name": name, "path": str(path)}, 201)
        elif parts == ["api", "validate"]:
            from .validator import validate_skill

            data = self._body_json()
            raw_name = data.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise StoreError("skill name must be a non-empty string")
            name = raw_name.strip()
            record = self.store.get(name)
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
        elif parts == ["api", "rebuild"]:
            self._send_json(self.store.db_rebuild())
        elif parts == ["api", "resync"]:
            self._send_json(self.store.resync())
        else:
            self._send_error(404, "unknown endpoint")

    # -- PATCH routes -----------------------------------------------------

    def _route_patch(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query)
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            data = self._body_json()
            fields = _validated_skill_fields(data)
            if scope != "global":
                from .scopes import edit_skill as _edit_skill

                self._send_json(_edit_skill(scope, parts[2], **fields))
                return
            self._send_json(self.store.edit(parts[2], **fields))
        else:
            self._send_error(404, "unknown endpoint")

    # -- DELETE routes ----------------------------------------------------

    def _delete_route(self, parts: list[str], qs: dict[str, list[str]]) -> None:
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            purge = qs.get("purge", ["0"])[0] in ("1", "true", "yes")
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                from .scopes import remove_skill as _remove_skill

                self._send_json(_remove_skill(scope, parts[2], purge=purge))
                return
            self._send_json(self.store.remove(parts[2], purge=purge))
        elif len(parts) == 4 and parts[:3] == ["api", "catalog", "profiles"]:
            from .catalog import delete_profile

            self._send_json(delete_profile(self.store.data_dir, parts[3]))
        else:
            self._send_error(404, "unknown endpoint")

    def _route_delete(self):
        self._delete_route(self._parts(), parse_qs(urlparse(self.path).query))

    # -- PUT routes -------------------------------------------------------

    def _route_put(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query)
        ctype = self.headers.get("Content-Type", "")
        if parts == ["api", "import"] and ctype.startswith("multipart/form-data"):
            boundary_m = re.search(r"boundary=([^;]+)", ctype)
            if not boundary_m:
                self._send_error(400, "multipart boundary missing")
                return
            file_parts = _parse_multipart(self._read_body(), boundary_m.group(1).strip('"'))
            uploaded = self._upload_folder(file_parts)
            self._send_json(uploaded)
        elif parts == ["api", "import"]:
            filename = os.path.basename(
                qs.get("filename", ["skills-import.tar.gz"])[0] or "skills-import.tar.gz"
            )
            if not filename.endswith((".tar.gz", ".tgz", ".tar", ".zip")):
                self._send_error(400, "unsupported archive type (use .tar.gz/.tgz/.tar/.zip)")
                return
            force = qs.get("force", ["0"])[0] in ("1", "true", "yes")
            full = qs.get("full", ["0"])[0] in ("1", "true", "yes")
            try:
                raw = self._read_body()
            except StoreError as exc:
                self._send_error(413 if "too large" in str(exc) else 400, str(exc))
                return
            if not raw:
                self._send_error(400, "empty archive body")
                return
            target = Path(tempfile.mkdtemp(prefix="skillsmgr-webui-")) / filename
            try:
                target.write_bytes(raw)
                try:
                    result = self.store.import_(target, force=force, full=full)
                except StoreError as exc:
                    self._send_error(400, str(exc))
                    return
            finally:
                shutil.rmtree(target.parent, ignore_errors=True)
            self._send_json(result)
        else:
            self._send_error(404, "unknown endpoint")

    def _upload_folder(self, file_parts: list[dict]) -> dict:
        """Install skills from an uploaded skill folder (webkitdirectory)."""
        return upload_folder(
            file_parts,
            self.store.add,
            max_parts=MAX_UPLOAD_PARTS,
            max_bytes=MAX_BODY_BYTES,
        )


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
            from .scopes import set_global_store

            set_global_store(self.store)  # type: ignore[attr-defined]
        super().process_request_thread(request, client_address)


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
        self.httpd = _StoreBoundHTTPServer((host, port), WebAppHandler)
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
        try:
            from .scopes import set_global_store as _set_global_store

            _set_global_store(store)
        except Exception as exc:
            _diagnose("could not bind the server store to the scope adapter", exc)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _open_browser(url: str) -> None:
    try:
        subprocess.Popen(
            ["xdg-open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


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

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
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .store import Store, StoreError, SkillNotFound
from .diagnostics import diagnose as _diagnose
from .web_security import RequestError, validate_mutation_request
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
        self.wfile.write(body)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _send_json(self, obj, status: int = 200) -> None:
        self._send(status, _json_bytes(obj))

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _read_body(self, limit: int = MAX_BODY_BYTES) -> bytes:
        raw_length = self.headers.get("Content-Length") or "0"
        try:
            length = int(str(raw_length).strip())
        except ValueError:
            raise StoreError("invalid Content-Length")
        if length < 0:
            raise StoreError("invalid Content-Length")
        if length > limit:
            raise StoreError("request body too large")
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
            self._route_get()
        except Exception as exc:
            self._handle_exception(exc)

    def do_POST(self):
        try:
            self._validate_mutation_request()
            self._route_post()
        except Exception as exc:
            self._handle_exception(exc)

    def do_PATCH(self):
        try:
            self._validate_mutation_request()
            self._route_patch()
        except Exception as exc:
            self._handle_exception(exc)

    def do_DELETE(self):
        try:
            self._validate_mutation_request()
            self._route_delete()
        except Exception as exc:
            self._handle_exception(exc)

    def do_PUT(self):
        try:
            self._validate_mutation_request()
            self._route_put()
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

    def _validate_mutation_request(self) -> None:
        validate_mutation_request(
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
        if parts == ["api", "skills"]:
            scope = (qs.get("scope", [""])[0] or "").strip()
            q = (qs.get("q", [""])[0] or "").strip()
            if scope == "all":
                if q:
                    from .scopes import search_all as _search_all

                    self._send_json(_search_all(q, scope_id="all", store=self.store))
                else:
                    from .scopes import list_all as _list_all

                    self._send_json(_list_all())
                return
            if scope and scope != "global":
                from .scopes import scan_scope as _scan_scope, search_all as _search_all

                if q:
                    self._send_json(_search_all(q, scope_id=scope))
                else:
                    self._send_json(_scan_scope(scope))
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
                try:
                    from .tokens import estimate as _est

                    for r in rows:
                        p = self.store.skills_dir / r["name"]
                        raw = ""
                        for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                            if cand.is_file():
                                raw = cand.read_text(encoding="utf-8")
                                break
                        tok = _est(raw)
                        r["tokens"] = tok["tokens"]
                        r["tokens_method"] = tok["method"]
                        r["tokens_pct"] = tok["pct_window"]
                        r["chars"] = tok["chars"]
                except Exception:
                    pass
                self._send_json(rows)
            else:
                rows = self.store.list()
                for r in rows:
                    r.setdefault("scope", "global")
                    r.setdefault("scope_label", "Global")
                # Token enrichment for list rows
                try:
                    from .tokens import estimate as _est2

                    for r in rows:
                        p = self.store.skills_dir / r["name"]
                        raw = ""
                        for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                            if cand.is_file():
                                raw = cand.read_text(encoding="utf-8")
                                break
                        tok = _est2(raw)
                        r["tokens"] = tok["tokens"]
                        r["tokens_method"] = tok["method"]
                        r["tokens_pct"] = tok["pct_window"]
                        r["chars"] = tok["chars"]
                except Exception:
                    pass
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

                    self._send_json(_search_all(q, scope_id="all", store=self.store))
                else:
                    self._send_json(self.store.search(q))
            elif scope == "global":
                from .scopes import search_all as _search_all

                self._send_json(_search_all(q, scope_id="global", store=self.store))
            else:
                from .scopes import search_all as _search_all

                self._send_json(_search_all(q, scope_id=scope))
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

                self._send_json(_get_skill(scope, parts[2]))
                return
            # Use injected store for correct data_dir in tests, with token enrichment
            rec = self.store.get(parts[2])
            rec.setdefault("scope", "global")
            rec.setdefault("scope_label", "Global")
            try:
                from .tokens import estimate as _estD

                p = self.store.skills_dir / parts[2]
                raw = ""
                for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                    if cand.is_file():
                        raw = cand.read_text(encoding="utf-8")
                        break
                tok = _estD(raw)
                rec["tokens"] = tok["tokens"]
                rec["tokens_method"] = tok["method"]
                rec["tokens_pct"] = tok["pct_window"]
                rec["chars"] = tok["chars"]
                rec["lines"] = tok["lines"]
                rec["body_tokens"] = _estD(rec.get("body") or "")["tokens"]
                rec["frontmatter_tokens"] = max(0, tok["tokens"] - rec["body_tokens"])
            except Exception:
                pass
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

                scopes = _list_scopes()
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
                    from .scopes import list_all as _list_all

                    st["largest"] = sorted(_list_all(), key=lambda r: r.get("tokens", 0), reverse=True)[:5]
                    st["largest"] = [{"name": r["name"], "scope": r.get("scope"), "tokens": r.get("tokens", 0)} for r in st["largest"]]
                except Exception:
                    st["largest"] = []
                # Whether exact counting is available.
                try:
                    from .tokens import _HAS_TIKTOKEN as _ht

                    st["has_tiktoken"] = bool(_ht)
                except Exception:
                    st["has_tiktoken"] = False
            except Exception:
                pass
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
                    except Exception:
                        pass
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
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            report = self.store.doctor()
            if scope == "all":
                try:
                    from .scopes import find_duplicates as _dupes
                    from .scopes import list_scopes as _lscopes

                    report["scopes"] = _lscopes()
                    report["duplicates"] = _dupes()
                except Exception:
                    pass
            self._send_json(report)
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
            self.wfile.write(body)
        else:
            self._send_error(404, "unknown endpoint")

    # -- POST routes ------------------------------------------------------

    def _route_post(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query)
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
            raw_source = data.get("source")
            if not isinstance(raw_source, str):
                raise StoreError("source must be a string")
            source = raw_source.strip()
            if not source:
                raise StoreError("source is required (e.g. vercel-labs/agent-skills)")
            if not re.fullmatch(r"[A-Za-z0-9_@./:+-]+", source) or source.startswith("-"):
                raise StoreError("invalid source value")
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
                    a = str(a)
                    if not re.fullmatch(r"[A-Za-z0-9_@./:+-]+", a) or a.startswith("-"):
                        raise StoreError(f"invalid agent value {a!r}")
                    cmd_parts.extend(["-a", a])
            if skills_filter:
                for s in skills_filter:
                    s = str(s)
                    if not re.fullmatch(r"[A-Za-z0-9_@./:+-]+", s) or s.startswith("-"):
                        raise StoreError(f"invalid skill value {s!r}")
                    cmd_parts.extend(["-s", s])
            if copy_mode:
                cmd_parts.append("--copy")
            if list_only:
                cmd_parts.append("-l")
            cmd_str = " ".join(cmd_parts)
            if not data.get("run"):
                self._send_json({"command": cmd_str, "runner": runner, "source": source, "executed": False})
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
        if parts == ["api", "scopes"]:
            self._send_error(404, "unknown endpoint")
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
                {
                    "valid": result.valid,
                    "issues": [
                        {"level": issue.level, "key": issue.key, "message": issue.message}
                        for issue in result.issues
                    ],
                }
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

    def _route_delete(self):
        parts = self._parts()
        qs = parse_qs(urlparse(self.path).query)
        if len(parts) == 3 and parts[:2] == ["api", "skills"]:
            purge = qs.get("purge", ["0"])[0] in ("1", "true", "yes")
            scope = (qs.get("scope", ["global"])[0] or "global").strip() or "global"
            if scope != "global":
                from .scopes import remove_skill as _remove_skill

                self._send_json(_remove_skill(scope, parts[2], purge=purge))
                return
            self._send_json(self.store.remove(parts[2], purge=purge))
        else:
            self._send_error(404, "unknown endpoint")

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
            if not filename.endswith((".tar.gz", ".tgz", ".tar")):
                self._send_error(400, "unsupported archive type (use .tar.gz/.tgz/.tar)")
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


class WebAppServer:
    def __init__(self, store: Store, host: str = "127.0.0.1", port: int = 0):
        normalized_host = host.strip().lower()
        is_localhost_name = normalized_host == "localhost"
        try:
            is_loopback = ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            is_loopback = False
        if not (is_localhost_name or is_loopback):
            raise StoreError("web UI host must be loopback (127.0.0.1, ::1, or localhost)")
        self.httpd = ThreadingHTTPServer((host, port), WebAppHandler)
        self.httpd.store = store  # type: ignore[attr-defined]
        self.host = host
        self.port = self.httpd.server_address[1]
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
        try:
            from .scopes import set_global_store as _set_global_store

            _set_global_store(store)
        except Exception:
            pass

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

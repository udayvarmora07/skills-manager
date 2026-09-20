"""Bounded skills.sh registry access, caching, snapshots, and provenance.

The registry is deliberately an optional network edge.  Nothing in this
module contacts the network at import time, credentials are read only for a
request, and downloaded content is validated before it can be materialized.
The cache is an optimization, never evidence that a skill is trusted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .store import StoreError


REGISTRY_BASE_URL = "https://skills.sh"
REGISTRY_API_BASE = f"{REGISTRY_BASE_URL}/api/v1"
REGISTRY_SKILLS_PATH = "/api/v1/skills"
REGISTRY_SEARCH_PATH = "/api/v1/skills/search"
REGISTRY_CURATED_PATH = "/api/v1/skills/curated"
REGISTRY_DOWNLOAD_PATH = "/api/download"
REGISTRY_CACHE_DIRNAME = "registry-cache"
REGISTRY_REVIEW_DIRNAME = "registry-reviews"
PROVENANCE_FILENAME = ".skillsmgr-provenance.json"

MAX_QUERY_LENGTH = 256
MAX_URL_LENGTH = 2048
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 12 * 1024 * 1024
MAX_FILES = 128
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 8 * 1024 * 1024
MAX_PATH_DEPTH = 8
MAX_CACHE_TTL = 3600
DEFAULT_CACHE_TTL = 300
MAX_REVIEW_BYTES = 16 * 1024 * 1024
MAX_REVIEW_AGE = 24 * 60 * 60
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_REVIEW_ID = re.compile(r"^[0-9a-f]{32}$")
_REVIEW_CREDENTIAL_KEYS = {
    "authorization", "bearer", "credential", "password", "secret", "token",
}
_ALLOWED_HOSTS = frozenset({"skills.sh", "www.skills.sh"})
_CACHE_STATES = frozenset({"miss", "fresh", "stale", "refreshed"})


class RegistryError(StoreError):
    """Raised when a registry request, response, cache, or snapshot is unsafe."""


def _now() -> float:
    return time.time()


def _iso(timestamp: float | None = None) -> str:
    return datetime.fromtimestamp(timestamp or _now(), timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _registry_url(url: str) -> str:
    """Validate that *url* is a registry HTTPS URL with no user-controlled host."""
    if not isinstance(url, str) or len(url) > MAX_URL_LENGTH:
        raise RegistryError("registry URL is invalid or too long")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise RegistryError("registry URL must use the skills.sh HTTPS host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise RegistryError("registry URL cannot carry a custom port") from exc
    if parsed.username or parsed.password or port is not None:
        raise RegistryError("registry URL cannot carry credentials or a custom port")
    if not parsed.path.startswith("/api/"):
        raise RegistryError("registry URL must target a documented API endpoint")
    return url


def _bounded_text(value: object, label: str, limit: int = MAX_QUERY_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{label} must be a non-empty string")
    value = value.strip()
    if len(value) > limit or "\x00" in value:
        raise RegistryError(f"{label} is too long or contains a NUL byte")
    return value


def _cache_ttl(headers: object, default: int) -> int:
    value = ""
    if headers is not None:
        try:
            value = headers.get("Cache-Control", "")
        except AttributeError:
            value = ""
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d+)", str(value), re.I)
    ttl = int(match.group(1)) if match else default
    return max(1, min(MAX_CACHE_TTL, ttl))


def _read_limited(response, limit: int) -> bytes:
    try:
        body = response.read(limit + 1)
    except (OSError, ValueError) as exc:
        raise RegistryError(f"could not read registry response: {exc}") from exc
    if not isinstance(body, bytes):
        raise RegistryError("registry response body was not bytes")
    if len(body) > limit:
        raise RegistryError(f"registry response exceeds {limit} bytes")
    return body


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Allow redirects only while the registry host policy remains true."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _registry_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_join(root: Path, relative: str, *, inspect_symlinks: bool = True) -> Path:
    """Return a path below *root*, rejecting traversal and symlink components."""
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise RegistryError("snapshot path is invalid")
    if "\\" in relative:
        raise RegistryError("snapshot paths must use POSIX separators")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise RegistryError("snapshot path escapes its staging directory")
    if relative != "/".join(path.parts):
        raise RegistryError("snapshot path is not canonical")
    if len(path.parts) > MAX_PATH_DEPTH:
        raise RegistryError(f"snapshot path exceeds depth {MAX_PATH_DEPTH}")
    candidate = root.joinpath(*path.parts)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RegistryError("snapshot path escapes its staging directory") from exc
    if not inspect_symlinks:
        return candidate
    current = root
    for part in path.parts[:-1]:
        current = current / part
        try:
            if current.is_symlink():
                raise RegistryError("snapshot path contains a symlink")
        except OSError as exc:
            raise RegistryError(f"could not inspect snapshot path: {exc}") from exc
    try:
        if candidate.is_symlink():
            raise RegistryError("snapshot path contains a symlink")
    except OSError as exc:
        raise RegistryError(f"could not inspect snapshot path: {exc}") from exc
    return candidate


def _reject_symlink_ancestors(path: Path) -> None:
    """Reject existing symlinks in a caller-provided destination ancestry."""
    current = Path(os.path.abspath(path))
    while True:
        try:
            if current.is_symlink():
                raise RegistryError("staging path contains a symlink ancestor")
        except OSError as exc:
            raise RegistryError(f"could not inspect staging path: {exc}") from exc
        if current.parent == current:
            return
        current = current.parent


def snapshot_hash(files: list[dict]) -> str:
    """Hash a snapshot with explicit path/content boundaries.

    Length framing prevents a path/content pair from being confused with a
    different pair that has the same concatenated byte stream.  The result is
    stable across platforms because paths are sorted POSIX text and all
    framing uses big-endian unsigned lengths.
    """
    digest = hashlib.sha256()
    for entry in sorted(files, key=lambda item: item["path"]):
        path = entry["path"].encode("utf-8")
        contents = entry["contents"].encode("utf-8")
        digest.update(len(path).to_bytes(8, "big"))
        digest.update(path)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def registry_snapshot_hash(files: list[dict]) -> str:
    """Compute the skills.sh-compatible snapshot hash.

    The upstream registry hashes sorted POSIX paths and UTF-8 file contents in
    sequence. Keep this separate from ``snapshot_hash``: the latter is the
    manager's framed local-integrity hash and is intentionally unambiguous.
    """
    digest = hashlib.sha256()
    for entry in sorted(files, key=lambda item: item["path"]):
        digest.update(entry["path"].encode("utf-8"))
        digest.update(entry["contents"].encode("utf-8"))
    return digest.hexdigest()


def validate_snapshot(payload: object) -> dict:
    """Validate and normalize a registry snapshot response."""
    if not isinstance(payload, dict):
        raise RegistryError("registry snapshot must be an object")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise RegistryError("registry snapshot must contain files")
    if len(raw_files) > MAX_FILES:
        raise RegistryError(f"registry snapshot has more than {MAX_FILES} files")
    files: list[dict] = []
    seen: set[str] = set()
    total = 0
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise RegistryError("registry snapshot file must be an object")
        path = raw.get("path")
        contents = raw.get("contents")
        if not isinstance(path, str) or not isinstance(contents, str):
            raise RegistryError("registry snapshot files must contain text path and contents")
        if path != path.strip():
            raise RegistryError("registry snapshot paths cannot have surrounding whitespace")
        if path == PROVENANCE_FILENAME:
            raise RegistryError("registry snapshots cannot include the manager provenance sidecar")
        _safe_join(Path("."), path, inspect_symlinks=False)
        if path in seen:
            raise RegistryError(f"registry snapshot contains duplicate path {path!r}")
        seen.add(path)
        size = len(contents.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise RegistryError(f"registry file {path!r} exceeds {MAX_FILE_BYTES} bytes")
        total += size
        if total > MAX_TOTAL_FILE_BYTES:
            raise RegistryError(f"registry snapshot exceeds {MAX_TOTAL_FILE_BYTES} bytes")
        files.append({"path": path, "contents": contents})
    if not any(item["path"] == "SKILL.md" for item in files):
        raise RegistryError("registry snapshot does not contain a root SKILL.md")
    supplied = payload.get("hash")
    if supplied is not None and (not isinstance(supplied, str) or not _HEX64.fullmatch(supplied)):
        raise RegistryError("registry snapshot hash must be a SHA-256 hex string")
    computed = snapshot_hash(files)
    registry_hash = registry_snapshot_hash(files)
    if supplied is not None and supplied.lower() != registry_hash:
        raise RegistryError("registry snapshot hash does not match its files")
    result = {key: value for key, value in payload.items() if key != "files"}
    result["files"] = files
    result["hash"] = supplied.lower() if isinstance(supplied, str) else None
    result["snapshot_hash"] = computed
    result["registry_hash"] = registry_hash
    result["hash_verified"] = supplied is not None
    return result


def _review_dir(data_dir: str | Path) -> Path:
    root = Path(data_dir).expanduser()
    return root / REGISTRY_REVIEW_DIRNAME


def _review_path(data_dir: str | Path, review_id: str) -> Path:
    if not isinstance(review_id, str) or not _REVIEW_ID.fullmatch(review_id):
        raise RegistryError("registry review id is invalid")
    directory = _review_dir(data_dir)
    _reject_symlink_ancestors(directory)
    return directory / f"{review_id}.json"


def _ensure_review_credential_free(value: object) -> None:
    """Reject credential-shaped keys before review data reaches disk."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = key.lower().replace("-", "_") if isinstance(key, str) else ""
            if normalized_key in _REVIEW_CREDENTIAL_KEYS or any(
                part in _REVIEW_CREDENTIAL_KEYS for part in normalized_key.split("_")
            ):
                raise RegistryError("registry review cannot contain credential fields")
            _ensure_review_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            _ensure_review_credential_free(nested)


def write_registry_review(data_dir: str | Path, snapshot: dict, inspection: dict) -> dict:
    """Persist a private, expiring snapshot for a separate commit transaction."""
    normalized = validate_snapshot(snapshot)
    if not isinstance(inspection, dict):
        raise RegistryError("registry review inspection must be an object")
    _ensure_review_credential_free(inspection)
    review_id = secrets.token_hex(16)
    now = _now()
    review_snapshot = {
        key: normalized.get(key)
        for key in (
            "id", "source", "slug", "page_url", "api_url", "hash", "remote_hash",
            "snapshot_hash",
            "registry_hash", "hash_verified", "normalization", "files", "_registry",
        )
        if normalized.get(key) is not None
    }
    metadata = review_snapshot.get("_registry")
    if not isinstance(metadata, dict):
        metadata = {}
    review_snapshot["_registry"] = {
        key: metadata.get(key)
        for key in ("cache_state", "stale", "url")
        if metadata.get(key) is not None
    }
    record = {
        "version": 1,
        "review_id": review_id,
        "status": "pending",
        "created_at": _iso(now),
        "expires_epoch": now + MAX_REVIEW_AGE,
        "snapshot": review_snapshot,
        "inspection": inspection,
    }
    try:
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RegistryError(f"registry review is not JSON-safe: {exc}") from exc
    if len(encoded) > MAX_REVIEW_BYTES:
        raise RegistryError("registry review exceeds the review size limit")
    directory = _review_dir(data_dir)
    path = _review_path(data_dir, review_id)
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        fd, temporary = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except OSError as exc:
        raise RegistryError(f"could not write registry review: {exc}") from exc
    return registry_review_public(record)


def _validate_review(value: object) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise RegistryError("registry review has an invalid header")
    review_id = value.get("review_id")
    if not isinstance(review_id, str) or not _REVIEW_ID.fullmatch(review_id):
        raise RegistryError("registry review id is invalid")
    if value.get("status") not in {"pending", "committed"}:
        raise RegistryError("registry review status is invalid")
    if not isinstance(value.get("expires_epoch"), (int, float)):
        raise RegistryError("registry review expiry is invalid")
    if value["expires_epoch"] <= _now():
        raise RegistryError("registry review has expired; fetch it again")
    snapshot = validate_snapshot(value.get("snapshot"))
    if not isinstance(value.get("inspection"), dict):
        raise RegistryError("registry review inspection is invalid")
    result = dict(value)
    result["snapshot"] = snapshot
    return result


def read_registry_review(data_dir: str | Path, review_id: str) -> dict:
    """Read one pending registry review without contacting the network."""
    path = _review_path(data_dir, review_id)
    if not path.is_file() or path.is_symlink():
        raise RegistryError("registry review was not found")
    try:
        if path.stat().st_size > MAX_REVIEW_BYTES:
            raise RegistryError("registry review exceeds the review size limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RegistryError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise RegistryError(f"registry review is unreadable: {exc}") from exc
    result = _validate_review(value)
    if result["status"] != "pending":
        raise RegistryError("registry review has already been committed")
    return result


def registry_review_public(record: dict) -> dict:
    """Return review metadata without including staged file contents."""
    snapshot = record.get("snapshot", {})
    registry_meta = snapshot.get("_registry", {}) if isinstance(snapshot, dict) else {}
    return {
        "review_id": record["review_id"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": _iso(float(record["expires_epoch"])),
        "registry": {
            "id": snapshot.get("id"),
            "source": snapshot.get("source"),
            "slug": snapshot.get("slug"),
            "page_url": snapshot.get("page_url"),
            "api_url": snapshot.get("api_url"),
            "remote_hash": snapshot.get("remote_hash", snapshot.get("hash")),
            "snapshot_hash": snapshot.get("snapshot_hash"),
            "registry_hash": snapshot.get("registry_hash"),
            "hash_verified": snapshot.get("hash_verified", False),
            "normalization": snapshot.get("normalization"),
            "cache_state": registry_meta.get("cache_state", "unknown"),
            "file_count": len(snapshot.get("files", [])),
        },
        "inspection": record["inspection"],
    }


def mark_registry_review_committed(data_dir: str | Path, review_id: str) -> dict:
    """Mark a successfully applied review so it cannot be replayed."""
    path = _review_path(data_dir, review_id)
    try:
        value = _validate_review(json.loads(path.read_text(encoding="utf-8")))
        value["status"] = "committed"
        value["committed_at"] = _iso()
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        fd, temporary = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except RegistryError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise RegistryError(f"could not mark registry review committed: {exc}") from exc
    return registry_review_public(value)


def _validate_listing(payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RegistryError("registry listing response has an invalid shape")
    return payload


def _validate_detail(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise RegistryError("registry detail response has an invalid shape")
    for field in ("id", "source", "slug"):
        if field in payload and not isinstance(payload[field], str):
            raise RegistryError(f"registry detail field {field!r} is invalid")
    return payload


def _reference(spec: str) -> dict:
    try:
        from .insights import registry_reference

        return registry_reference(spec)
    except (ValueError, TypeError) as exc:
        raise RegistryError(str(exc)) from exc


class RegistryClient:
    """Access the authenticated skills.sh API with bounded local caching."""

    def __init__(self, data_dir: str | Path | None = None, *, opener=None,
                 token: str | None = None, timeout: float = 15.0,
                 now=None):
        if timeout <= 0 or timeout > 120:
            raise RegistryError("registry timeout must be between 0 and 120 seconds")
        self.data_dir = Path(data_dir).expanduser() if data_dir is not None else None
        self.cache_dir = self.data_dir / REGISTRY_CACHE_DIRNAME if self.data_dir else None
        self._opener = opener or build_opener(_SafeRedirectHandler())
        self._token = token
        self.timeout = timeout
        self._clock = now or _now

    def _credential(self) -> str | None:
        value = self._token
        if value is None:
            value = os.environ.get("SKILLS_MANAGER_REGISTRY_TOKEN")
        if value is None:
            value = os.environ.get("VERCEL_OIDC_TOKEN")
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise RegistryError("registry token is empty")
        if value is not None and len(value) > 8192:
            raise RegistryError("registry token is too long")
        return value.strip() if isinstance(value, str) else value

    def _url(self, path: str, query: dict | None = None) -> str:
        if not path.startswith("/api/"):
            raise RegistryError("unsupported registry endpoint")
        url = urljoin(REGISTRY_BASE_URL, path)
        if query:
            url += "?" + urlencode(query)
        return _registry_url(url)

    def _cache_path(self, url: str, auth_scope: str) -> Path | None:
        if self.cache_dir is None:
            return None
        _reject_symlink_ancestors(self.cache_dir)
        if self.cache_dir.exists() and not self.cache_dir.is_dir():
            raise RegistryError("registry cache path is not a directory")
        key = hashlib.sha256((auth_scope + "\x00" + url).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, url: str, auth_scope: str) -> dict | None:
        path = self._cache_path(url, auth_scope)
        if path is None:
            return None
        if os.path.lexists(path) and path.is_symlink():
            raise RegistryError("registry cache entry cannot be a symlink")
        if not path.is_file():
            return None
        try:
            if path.stat().st_size > MAX_CACHE_BYTES:
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return None
        if (
            not isinstance(value, dict)
            or value.get("url") != url
            or value.get("auth_scope") != auth_scope
        ):
            return None
        if not isinstance(value.get("payload"), (dict, list)):
            return None
        return value

    def _write_cache(self, url: str, payload: object, headers: object,
                     fetched_at: float, auth_scope: str, default_ttl: int) -> None:
        path = self._cache_path(url, auth_scope)
        if path is None:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.cache_dir, 0o700)
            ttl = _cache_ttl(headers, default_ttl)
            value = {
                "version": 1,
                "url": url,
                "auth_scope": auth_scope,
                "fetched_at": _iso(fetched_at),
                "expires_at": _iso(fetched_at + ttl),
                "expires_epoch": fetched_at + ttl,
                "payload": payload,
            }
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            if len(encoded) > MAX_CACHE_BYTES:
                return
            fd, temporary = tempfile.mkstemp(prefix=".registry-", suffix=".tmp", dir=self.cache_dir)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        except OSError as exc:
            raise RegistryError(f"could not write registry cache: {exc}") from exc

    def _request_json(self, url: str, *, default_ttl: int = DEFAULT_CACHE_TTL,
                      allow_stale: bool = False) -> tuple[object, dict]:
        token = self._credential()
        auth_scope = (
            "authenticated:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
            if token else "anonymous"
        )
        cached = self._read_cache(url, auth_scope)
        now = self._clock()
        if cached is not None:
            expires = cached.get("expires_epoch")
            if isinstance(expires, (int, float)) and expires > now:
                return cached["payload"], {"cache_state": "fresh", "stale": False, "url": url}
        headers = {"Accept": "application/json", "User-Agent": "skills-manager/registry"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers, method="GET")
        try:
            if callable(self._opener):
                response = self._opener(request, timeout=self.timeout)
            else:
                response = self._opener.open(request, timeout=self.timeout)
            try:
                final_url = response.geturl() if hasattr(response, "geturl") else url
                _registry_url(final_url)
                status = getattr(response, "status", None) or response.getcode()
                if status < 200 or status >= 300:
                    raise RegistryError(f"registry request failed with HTTP {status}")
                content_type = ""
                response_headers = getattr(response, "headers", None)
                if response_headers is not None:
                    content_type = str(response_headers.get("Content-Type", ""))
                if content_type and "json" not in content_type.lower():
                    raise RegistryError("registry response was not JSON")
                body = _read_limited(response, MAX_RESPONSE_BYTES)
            finally:
                close = getattr(response, "close", None)
                if close:
                    close()
        except HTTPError as exc:
            retry = exc.headers.get("Retry-After") if exc.headers else None
            suffix = f"; retry after {retry}s" if retry else ""
            raise RegistryError(f"registry request failed with HTTP {exc.code}{suffix}") from exc
        except URLError as exc:
            if cached is not None and allow_stale:
                return cached["payload"], {"cache_state": "stale", "stale": True, "url": url}
            raise RegistryError(f"could not reach registry: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            if cached is not None and allow_stale:
                return cached["payload"], {"cache_state": "stale", "stale": True, "url": url}
            raise RegistryError(f"registry request failed: {exc}") from exc
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RegistryError(f"registry response was not valid UTF-8 JSON: {exc}") from exc
        self._write_cache(url, payload, response_headers, now, auth_scope, default_ttl)
        state = "refreshed" if cached is not None else "miss"
        return payload, {"cache_state": state, "stale": False, "url": url}

    @staticmethod
    def _with_meta(payload: object, meta: dict) -> dict:
        if not isinstance(payload, dict):
            raise RegistryError("registry response cannot carry metadata")
        result = dict(payload)
        result["_registry"] = dict(meta)
        return result

    def browse(self, *, page: int = 0, per_page: int = 100, view: str = "all-time",
               allow_stale: bool = False) -> dict:
        """Return one bounded leaderboard page."""
        if isinstance(page, bool) or not isinstance(page, int) or not 0 <= page <= 100000:
            raise RegistryError("registry page is out of bounds")
        if isinstance(per_page, bool) or not isinstance(per_page, int) or not 1 <= per_page <= 500:
            raise RegistryError("registry per_page must be between 1 and 500")
        view = _bounded_text(view, "registry view", 32)
        if view not in {"all-time", "trending", "hot"}:
            raise RegistryError("registry view must be all-time, trending, or hot")
        payload, meta = self._request_json(
            self._url(REGISTRY_SKILLS_PATH, {"page": page, "per_page": per_page, "view": view}),
            allow_stale=allow_stale,
        )
        return self._with_meta(_validate_listing(payload), meta)

    def search(self, query: str, *, limit: int = 50, owner: str | None = None,
               allow_stale: bool = False) -> dict:
        """Search the catalog with the registry's bounded query contract."""
        query = _bounded_text(query, "registry search query")
        if len(query) < 2:
            raise RegistryError("registry search query must contain at least 2 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise RegistryError("registry search limit must be between 1 and 200")
        query_params = {"q": query, "limit": limit}
        if owner is not None:
            query_params["owner"] = _bounded_text(owner, "registry owner", 128)
        payload, meta = self._request_json(
            self._url(REGISTRY_SEARCH_PATH, query_params), allow_stale=allow_stale
        )
        return self._with_meta(_validate_listing(payload), meta)

    def curated(self, *, allow_stale: bool = False) -> dict:
        """Return the registry's curated catalog."""
        payload, meta = self._request_json(
            self._url(REGISTRY_CURATED_PATH), default_ttl=MAX_CACHE_TTL,
            allow_stale=allow_stale,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RegistryError("registry curated response has an invalid shape")
        return self._with_meta(payload, meta)

    def detail(self, spec: str, *, allow_stale: bool = False) -> dict:
        """Return metadata for a registry skill id or skills.sh page URL."""
        reference = _reference(spec)
        if not reference.get("slug"):
            raise RegistryError("registry detail requires a skill id, not only a repository")
        source = str(reference["source"])
        slug = str(reference["slug"])
        path = REGISTRY_SKILLS_PATH + "/" + "/".join(
            quote(part, safe="") for part in (*source.split("/"), slug)
        )
        payload, meta = self._request_json(self._url(path), allow_stale=allow_stale)
        return self._with_meta(_validate_detail(payload), meta)

    def fetch(self, spec: str, *, expected_hash: str | None = None,
              allow_stale: bool = False) -> dict:
        """Fetch and validate a complete text snapshot for one registry skill."""
        reference = _reference(spec)
        if not reference.get("slug"):
            raise RegistryError("registry fetch requires a skill id, not only a repository")
        if expected_hash is not None and (not isinstance(expected_hash, str) or not _HEX64.fullmatch(expected_hash)):
            raise RegistryError("expected_hash must be a SHA-256 hex string")
        source = str(reference["source"])
        slug = str(reference["slug"])
        path = REGISTRY_SKILLS_PATH + "/" + "/".join(
            quote(part, safe="") for part in (*source.split("/"), slug)
        )
        payload, meta = self._request_json(self._url(path), allow_stale=allow_stale)
        result = validate_snapshot(payload)
        if expected_hash is not None and result["registry_hash"] != expected_hash.lower():
            raise RegistryError("fetched snapshot does not match expected_hash")
        result["id"] = reference.get("registry_id")
        result["source"] = source
        result["slug"] = slug
        result["page_url"] = reference.get("page_url")
        result["api_url"] = meta["url"]
        result["_registry"] = meta
        return result


def materialize_snapshot(snapshot: dict, staging_dir: str | Path) -> Path:
    """Atomically write a validated snapshot into a fresh staging directory."""
    normalized = validate_snapshot(snapshot)
    root = Path(staging_dir).expanduser()
    _reject_symlink_ancestors(root)
    if root.exists() and root.is_symlink():
        raise RegistryError("staging directory cannot be a symlink")
    if root.exists() and not root.is_dir():
        raise RegistryError("staging path must be a directory")
    try:
        if root.exists() and any(root.iterdir()):
            raise RegistryError("staging directory must be empty")
        root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
        os.chmod(temporary, 0o700)
    except OSError as exc:
        raise RegistryError(f"could not create staging directory: {exc}") from exc
    try:
        for entry in normalized["files"]:
            destination = _safe_join(temporary, entry["path"])
            try:
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                current = temporary
                for part in PurePosixPath(entry["path"]).parts[:-1]:
                    current = current / part
                    if current.is_symlink():
                        raise RegistryError("snapshot destination contains a symlink")
                destination.write_text(entry["contents"], encoding="utf-8", newline="")
                os.chmod(destination, 0o600)
            except OSError as exc:
                raise RegistryError(f"could not materialize {entry['path']!r}: {exc}") from exc
        backup = None
        if root.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{root.name}-old-", dir=root.parent))
            backup.rmdir()
            os.replace(root, backup)
        try:
            os.replace(temporary, root)
            temporary = None
        except OSError:
            if backup is not None and not root.exists():
                os.replace(backup, root)
            raise
        if backup is not None:
            backup.rmdir()
    except RegistryError:
        raise
    except OSError as exc:
        raise RegistryError(f"could not atomically materialize snapshot: {exc}") from exc
    finally:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
    return root


def provenance_for_snapshot(snapshot: dict) -> dict:
    """Build a credential-free provenance record for a fetched snapshot."""
    normalized = validate_snapshot(snapshot)
    files = [
        {
            "path": entry["path"],
            "sha256": hashlib.sha256(entry["contents"].encode("utf-8")).hexdigest(),
            "bytes": len(entry["contents"].encode("utf-8")),
        }
        for entry in normalized["files"]
    ]
    registry_meta = normalized.get("_registry") or {}
    return {
        "version": 1,
        "kind": "skills.sh",
        "id": normalized.get("id"),
        "source": normalized.get("source"),
        "slug": normalized.get("slug"),
        "page_url": normalized.get("page_url"),
        "api_url": normalized.get("api_url") or registry_meta.get("url"),
        "remote_hash": normalized.get("hash"),
        "registry_hash": normalized["registry_hash"],
        "local_snapshot_hash": normalized["snapshot_hash"],
        "hash_verified": bool(normalized.get("hash_verified")),
        "fetched_at": _iso(),
        "cache_state": registry_meta.get("cache_state", "unknown"),
        "normalization": normalized.get("normalization"),
        "files": files,
    }


def _validate_provenance(value: object) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1 or value.get("kind") != "skills.sh":
        raise RegistryError("registry provenance sidecar has an invalid header")
    allowed = {
        "version", "kind", "id", "source", "slug", "page_url", "api_url",
        "remote_hash", "registry_hash", "local_snapshot_hash", "hash_verified", "fetched_at",
        "normalization",
        "cache_state", "files",
    }
    if set(value) - allowed:
        raise RegistryError("registry provenance sidecar contains unsupported fields")
    required = ("id", "source", "slug", "api_url", "local_snapshot_hash", "files")
    if any(key not in value for key in required):
        raise RegistryError("registry provenance sidecar is missing required fields")
    for field in ("id", "source", "slug"):
        if (
            not isinstance(value[field], str)
            or not value[field].strip()
            or value[field] != value[field].strip()
            or len(value[field]) > MAX_QUERY_LENGTH
            or "\x00" in value[field]
        ):
            raise RegistryError(f"registry provenance field {field!r} is invalid")
    if value["id"] != f"{value['source']}/{value['slug']}":
        raise RegistryError("registry provenance id does not match source and slug")
    api_url = value.get("api_url")
    if not isinstance(api_url, str) or not api_url:
        raise RegistryError("registry provenance API URL is invalid")
    _registry_url(api_url)
    api_parsed = urlparse(api_url)
    if api_parsed.query or api_parsed.fragment:
        raise RegistryError("registry provenance API URL cannot contain query data")
    if value.get("page_url") is not None:
        page = value["page_url"]
        if not isinstance(page, str) or len(page) > MAX_URL_LENGTH:
            raise RegistryError("registry provenance page URL is invalid")
        parsed = urlparse(page)
        try:
            page_port = parsed.port
        except ValueError as exc:
            raise RegistryError("registry provenance page URL is invalid") from exc
        if (
            parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.username or parsed.password or page_port is not None
            or parsed.query or parsed.fragment
        ):
            raise RegistryError("registry provenance page URL is invalid")
    for field in ("remote_hash",):
        if value.get(field) is not None and (
            not isinstance(value[field], str) or not _HEX64.fullmatch(value[field])
        ):
            raise RegistryError(f"registry provenance field {field!r} is invalid")
    if value.get("registry_hash") is not None and (
        not isinstance(value["registry_hash"], str) or not _HEX64.fullmatch(value["registry_hash"])
    ):
        raise RegistryError("registry provenance registry hash is invalid")
    if value.get("normalization") is not None and (
        not isinstance(value["normalization"], str)
        or not value["normalization"].strip()
        or len(value["normalization"]) > MAX_QUERY_LENGTH
        or "\x00" in value["normalization"]
    ):
        raise RegistryError("registry provenance normalization is invalid")
    if (
        value.get("remote_hash") is not None
        and value.get("registry_hash") is not None
        and value["remote_hash"].lower() != value["registry_hash"].lower()
        and value.get("normalization") is None
    ):
        raise RegistryError("registry provenance hashes disagree")
    if not isinstance(value.get("local_snapshot_hash"), str) or not _HEX64.fullmatch(value["local_snapshot_hash"]):
        raise RegistryError("registry provenance local hash is invalid")
    if not isinstance(value.get("hash_verified", False), bool):
        raise RegistryError("registry provenance hash_verified is invalid")
    if value.get("fetched_at") is not None and (
        not isinstance(value["fetched_at"], str)
        or len(value["fetched_at"]) > 64
        or "\x00" in value["fetched_at"]
    ):
        raise RegistryError("registry provenance fetched_at is invalid")
    if value.get("cache_state", "unknown") not in _CACHE_STATES | {"unknown"}:
        raise RegistryError("registry provenance cache state is invalid")
    files = value.get("files")
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise RegistryError("registry provenance file manifest is invalid")
    seen: set[str] = set()
    total = 0
    for entry in files:
        if (
            not isinstance(entry, dict)
            or set(entry) - {"path", "sha256", "bytes"}
            or not isinstance(entry.get("path"), str)
        ):
            raise RegistryError("registry provenance file manifest entry is invalid")
        _safe_join(Path("."), entry["path"], inspect_symlinks=False)
        if entry["path"] in seen:
            raise RegistryError("registry provenance file manifest has duplicate paths")
        seen.add(entry["path"])
        if not isinstance(entry.get("sha256"), str) or not _HEX64.fullmatch(entry["sha256"]):
            raise RegistryError("registry provenance file hash is invalid")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] < 0:
            raise RegistryError("registry provenance file size is invalid")
        if entry["bytes"] > MAX_FILE_BYTES:
            raise RegistryError("registry provenance file size exceeds the registry limit")
        total += entry["bytes"]
    if total > MAX_TOTAL_FILE_BYTES or "SKILL.md" not in seen:
        raise RegistryError("registry provenance file manifest is incomplete")
    forbidden = {"token", "authorization", "bearer", "credential", "secret"}
    if forbidden & {str(key).lower() for key in value}:
        raise RegistryError("registry provenance cannot contain credentials")
    return dict(value)


def _local_file_manifest(root: Path) -> tuple[list[dict], str]:
    """Hash the local text files represented by a provenance sidecar."""
    files: list[dict] = []
    total = 0
    try:
        paths = sorted(path for path in root.rglob("*") if path.is_file())
    except OSError as exc:
        raise RegistryError(f"could not inspect skill files: {exc}") from exc
    for path in paths:
        if path.name == PROVENANCE_FILENAME:
            continue
        relative = path.relative_to(root).as_posix()
        _safe_join(root, relative)
        try:
            if path.is_symlink():
                raise RegistryError("provenance cannot describe symlinked files")
            raw_size = path.stat().st_size
            if raw_size > MAX_FILE_BYTES or total + raw_size > MAX_TOTAL_FILE_BYTES:
                raise RegistryError("local skill files exceed the registry limit")
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RegistryError(f"could not read skill file {relative!r}: {exc}") from exc
        size = len(contents.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise RegistryError("local skill file exceeds the registry limit")
        total += size
        files.append({
            "path": relative,
            "sha256": hashlib.sha256(contents.encode("utf-8")).hexdigest(),
            "bytes": size,
            "contents": contents,
        })
    if len(files) > MAX_FILES or total > MAX_TOTAL_FILE_BYTES or not any(
        entry["path"] == "SKILL.md" for entry in files
    ):
        raise RegistryError("local skill files do not form a valid registry snapshot")
    return files, snapshot_hash(files)


def _reconcile_provenance(root: Path, value: dict) -> None:
    actual, actual_hash = _local_file_manifest(root)
    expected = sorted([
        {key: entry[key] for key in ("path", "sha256", "bytes")}
        for entry in value["files"]
    ], key=lambda entry: entry["path"])
    actual_public = [
        {key: entry[key] for key in ("path", "sha256", "bytes")}
        for entry in actual
    ]
    if expected != actual_public:
        raise RegistryError("registry provenance does not match local skill files")
    if actual_hash != value["local_snapshot_hash"]:
        raise RegistryError("registry provenance local hash does not match local files")


def write_provenance(skill_dir: str | Path, provenance: dict) -> Path:
    """Atomically write a validated credential-free registry sidecar."""
    root = Path(skill_dir).expanduser()
    _reject_symlink_ancestors(root)
    if not root.is_dir() or root.is_symlink():
        raise RegistryError("skill directory for provenance does not exist safely")
    value = _validate_provenance(provenance)
    _reconcile_provenance(root, value)
    destination = root / PROVENANCE_FILENAME
    fd, temporary = tempfile.mkstemp(prefix=".provenance-", suffix=".tmp", dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except (OSError, TypeError, ValueError) as exc:
        Path(temporary).unlink(missing_ok=True)
        raise RegistryError(f"could not write registry provenance: {exc}") from exc
    return destination


def read_provenance(skill_dir: str | Path) -> dict | None:
    """Read and validate a registry provenance sidecar, if present."""
    root = Path(skill_dir).expanduser()
    _reject_symlink_ancestors(root)
    path = root / PROVENANCE_FILENAME
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        raise RegistryError("registry provenance sidecar cannot be a symlink")
    try:
        if path.stat().st_size > 256 * 1024:
            raise RegistryError("registry provenance sidecar is too large")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RegistryError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise RegistryError(f"registry provenance sidecar is unreadable: {exc}") from exc
    value = _validate_provenance(value)
    _reconcile_provenance(root, value)
    return value


__all__ = [
    "DEFAULT_CACHE_TTL",
    "MAX_FILES",
    "MAX_RESPONSE_BYTES",
    "PROVENANCE_FILENAME",
    "REGISTRY_REVIEW_DIRNAME",
    "REGISTRY_BASE_URL",
    "REGISTRY_DOWNLOAD_PATH",
    "RegistryClient",
    "RegistryError",
    "materialize_snapshot",
    "provenance_for_snapshot",
    "read_provenance",
    "read_registry_review",
    "registry_snapshot_hash",
    "snapshot_hash",
    "write_registry_review",
    "mark_registry_review_committed",
    "registry_review_public",
    "validate_snapshot",
    "write_provenance",
]

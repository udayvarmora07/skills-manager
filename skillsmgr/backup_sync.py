"""Review-first planning and apply seams for Git-oriented backup/sync.

Manifest planning remains pure. The optional integration below delegates
remote authentication to the user's Git configuration, stores only bounded
credential-free review evidence, and requires an explicit review, target,
snapshot, and approval before applying a candidate tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess  # nosec B404 - each subprocess call below uses trusted Git and bounded argv.
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .atomic_io import atomic_write_text, mutation_lock
from .source_lock import local_manifest, review_local_update, commit_local_update
from .validator import validate_skill_name


MAX_MANIFEST_SKILLS = 2048
MAX_MANIFEST_FILES = 256
MAX_NAME = 64
SYNC_REVIEW_DIRNAME = "sync-reviews"
MAX_SYNC_REVIEW_BYTES = 16 * 1024 * 1024
MAX_SYNC_REVIEW_AGE = 24 * 60 * 60
_REVIEW_ID = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_GIT_REVISION = re.compile(r"^[0-9a-fA-F]{40,64}$")
_REMOTE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REFSPEC = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+*^~-]{0,255}$")
_CREDENTIAL_KEYS = {"authorization", "bearer", "credential", "password", "secret", "token"}


class BackupSyncError(ValueError):
    """Raised when a dry-run manifest is unsafe or ambiguous."""


def _source_label(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BackupSyncError("source label must be a non-empty string")
    value = value.strip()
    if len(value) > 256 or "\x00" in value:
        raise BackupSyncError("source label is too long or contains a NUL byte")
    parsed = urlparse(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BackupSyncError("source label cannot contain credentials, query, or fragment data")
    return value


def _digest(value: object, label: str) -> str:
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str):
        value = value.strip()
        if len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value):
            return value.lower()
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    raise BackupSyncError(f"{label} must be text, bytes, or a SHA-256 digest")


def _skill_entry(name: str, value: object) -> dict:
    try:
        name = validate_skill_name(name)
    except ValueError as exc:
        raise BackupSyncError(str(exc)) from exc
    if isinstance(value, dict):
        digest = _digest(value.get("digest", ""), f"{name} digest")
        raw_metadata = value.get("metadata_digest")
        metadata = (
            None
            if raw_metadata is None
            else _digest(raw_metadata, f"{name} metadata_digest")
        )
        raw_files = value.get("files", [])
        if not isinstance(raw_files, list) or len(raw_files) > MAX_MANIFEST_FILES:
            raise BackupSyncError(f"{name} has too many manifest files")
        files = []
        for raw in raw_files:
            if not isinstance(raw, dict) or not isinstance(raw.get("path"), str):
                raise BackupSyncError(f"{name} has an invalid file manifest entry")
            path = raw["path"]
            if not path or path.startswith(("/", "\\")) or ".." in path.split("/") or "\\" in path:
                raise BackupSyncError(f"{name} has an unsafe file path")
            files.append({"path": path, "digest": _digest(raw.get("digest", ""), f"{name}/{path}")})
        files.sort(key=lambda item: item["path"])
        return {"digest": digest, "metadata_digest": metadata, "files": files}
    return {"digest": _digest(value, f"{name} digest"), "metadata_digest": None, "files": []}


def build_manifest(skills: dict, *, source: str) -> dict:
    """Normalize an exact skill manifest for local or remote comparison."""
    if not isinstance(skills, dict) or len(skills) > MAX_MANIFEST_SKILLS:
        raise BackupSyncError(f"manifest must contain at most {MAX_MANIFEST_SKILLS} skills")
    normalized = {name: _skill_entry(name, value) for name, value in skills.items()}
    return {
        "version": 1,
        "source": _source_label(source),
        "skills": {name: normalized[name] for name in sorted(normalized)},
        "credential_redacted": True,
    }


def _manifest_skills(manifest: dict, label: str) -> dict:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("skills"), dict):
        raise BackupSyncError(f"{label} manifest is invalid")
    return manifest["skills"]


def dry_run(local: dict, remote: dict, *, base: dict | None = None) -> dict:
    """Report exact local/remote changes and three-way conflicts."""
    local_skills = _manifest_skills(local, "local")
    remote_skills = _manifest_skills(remote, "remote")
    base_skills = _manifest_skills(base, "base") if base is not None else {}
    names = sorted(set(local_skills) | set(remote_skills) | set(base_skills))
    local_changes, remote_changes, conflicts = [], [], []
    for name in names:
        local_value = local_skills.get(name)
        remote_value = remote_skills.get(name)
        base_value = base_skills.get(name)
        if local_value != base_value:
            local_changes.append(name)
        if remote_value != base_value:
            remote_changes.append(name)
        if base is not None and local_value != base_value and remote_value != base_value and local_value != remote_value:
            conflicts.append(name)
    return {
        "local_source": local.get("source"),
        "remote_source": remote.get("source"),
        "local_changes": local_changes,
        "remote_changes": remote_changes,
        "conflicts": conflicts,
        "exact_change_count": len(set(local_changes) | set(remote_changes)),
        "dry_run": True,
        "credential_redacted": True,
        "plaintext_secrets": False,
        "remote_delete_requires_explicit_recovery": True,
    }


def _variant_name(name: str, suffix: str) -> str:
    candidate = f"{name}-{suffix}"
    if len(candidate) > MAX_NAME:
        candidate = f"{name[:MAX_NAME - len(suffix) - 1]}-{suffix}"
    return validate_skill_name(candidate)


def three_way_plan(base: dict, local: dict, remote: dict, *, strategy: str = "review") -> dict:
    """Plan conflict handling without choosing a destructive default."""
    if strategy not in {"review", "keep-mine", "use-remote", "keep-both"}:
        raise BackupSyncError("strategy must be review, keep-mine, use-remote, or keep-both")
    base_skills = _manifest_skills(base, "base")
    local_skills = _manifest_skills(local, "local")
    remote_skills = _manifest_skills(remote, "remote")
    names = sorted(set(base_skills) | set(local_skills) | set(remote_skills))
    decisions = []
    for name in names:
        before, mine, theirs = base_skills.get(name), local_skills.get(name), remote_skills.get(name)
        if mine == theirs:
            action = "keep-local" if mine is not None else "delete"
            decisions.append({"name": name, "action": action})
        elif mine == before:
            decisions.append({"name": name, "action": "use-remote"})
        elif theirs == before:
            decisions.append({"name": name, "action": "keep-mine"})
        elif strategy == "review":
            decisions.append({"name": name, "action": "conflict", "requires_review": True})
        elif strategy in {"keep-mine", "use-remote"}:
            decisions.append({"name": name, "action": strategy})
        else:
            decisions.append({
                "name": name,
                "action": "keep-both",
                "result_names": [_variant_name(name, "local"), _variant_name(name, "remote")],
                "requires_review": True,
            })
    return {
        "strategy": strategy,
        "decisions": decisions,
        "conflicts": [item["name"] for item in decisions if item["action"] == "conflict"],
        "writes": False,
        "retryable": True,
        "recovery": "create or verify a local snapshot before applying any approved plan",
        "credential_redacted": True,
    }


def interrupted_sync(completed: list[str], pending: list[str], snapshot: str | None) -> dict:
    """Describe a retry-safe interrupted operation without mutating state."""
    if not isinstance(completed, list) or not isinstance(pending, list):
        raise BackupSyncError("completed and pending must be lists")
    if snapshot is not None and (not isinstance(snapshot, str) or not snapshot.strip()):
        raise BackupSyncError("snapshot must be a non-empty id when present")
    return {
        "status": "interrupted",
        "completed": list(completed),
        "pending": list(pending),
        "retryable": True,
        "local_filesystem_valid": True,
        "snapshot": snapshot,
        "credential_redacted": True,
    }


def _iso(timestamp: float | None = None) -> str:
    return datetime.fromtimestamp(timestamp or time.time(), timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BackupSyncError(f"sync review is not JSON-safe: {exc}") from exc


def _ensure_credential_free(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower().replace("-", "_") if isinstance(key, str) else ""
            if normalized != "credential_redacted" and (
                normalized in _CREDENTIAL_KEYS
                or any(part in _CREDENTIAL_KEYS for part in normalized.split("_"))
            ):
                raise BackupSyncError("sync review cannot contain credential fields")
            _ensure_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            _ensure_credential_free(nested)


def _review_path(data_dir: str | Path, review_id: str) -> Path:
    if not isinstance(review_id, str) or not _REVIEW_ID.fullmatch(review_id):
        raise BackupSyncError("sync review id is invalid")
    directory = Path(data_dir).expanduser() / SYNC_REVIEW_DIRNAME
    for ancestor in (directory, *directory.parents):
        if ancestor.is_symlink():
            raise BackupSyncError("sync review path cannot contain a symlink")
    return directory / f"{review_id}.json"


def _normalize_manifest(manifest: dict, label: str) -> dict:
    if not isinstance(manifest, dict):
        raise BackupSyncError(f"{label} manifest is invalid")
    return build_manifest(manifest.get("skills"), source=manifest.get("source"))


def _manifest_digest(manifest: dict) -> str:
    return hashlib.sha256(_json_bytes(manifest)).hexdigest()


def _target_path(target: dict) -> Path:
    if not isinstance(target, dict) or not isinstance(target.get("physical_path"), str):
        raise BackupSyncError("sync target physical_path is required")
    if target.get("contained") is not True:
        raise BackupSyncError("sync target containment must be explicitly confirmed")
    path = Path(target["physical_path"]).expanduser()
    if not path.is_absolute() or "\x00" in str(path):
        raise BackupSyncError("sync target physical_path must be an absolute path")
    return path.resolve()


def _trusted_git() -> str:
    from .launcher_security import trusted_executable

    path = trusted_executable("git", which=shutil.which)
    if not path:
        raise BackupSyncError("a trusted Git executable is required for remote sync")
    return path


def _run_git(repo: str | Path, arguments: list[str], *, timeout: float = 60.0) -> str:
    root = Path(repo).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise BackupSyncError("Git repository is not an accessible directory")
    if timeout <= 0 or timeout > 300:
        raise BackupSyncError("Git timeout must be between 0 and 300 seconds")
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(  # nosec B603 - trusted executable, validated argv, and no shell.
            [_trusted_git(), "-C", str(root), "--no-optional-locks", *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackupSyncError("Git operation could not be started or completed") from exc
    if result.returncode != 0:
        raise BackupSyncError("Git operation failed; inspect the repository and configured authentication")
    output = result.stdout.strip()
    if len(output.encode("utf-8")) > 64 * 1024:
        raise BackupSyncError("Git operation returned too much output")
    return output


def git_remote_info(repo: str | Path, *, remote: str = "origin") -> dict:
    """Read safe remote metadata without exposing configured credentials."""
    if not isinstance(remote, str) or not _REMOTE_NAME.fullmatch(remote):
        raise BackupSyncError("Git remote name is invalid")
    url = _run_git(repo, ["remote", "get-url", "--", remote])
    url = _source_label(url)
    head = _run_git(repo, ["rev-parse", "--verify", "HEAD"])
    if not _GIT_REVISION.fullmatch(head):
        raise BackupSyncError("Git repository HEAD is not a valid revision")
    return {
        "remote": remote,
        "url": url,
        "revision": head.lower(),
        "auth_delegation": "Git credential helper or SSH agent; no credential is passed or persisted",
        "credential_redacted": True,
    }


def git_fetch(repo: str | Path, *, remote: str = "origin", refspec: str | None = None,
              timeout: float = 60.0) -> dict:
    """Fetch one configured Git remote without accepting a credential argument."""
    info = git_remote_info(repo, remote=remote)
    arguments = ["fetch", "--no-tags", remote]
    if refspec is not None:
        if not isinstance(refspec, str) or not _REFSPEC.fullmatch(refspec) or ".." in refspec:
            raise BackupSyncError("Git refspec is invalid")
        arguments.append(refspec)
    _run_git(repo, arguments, timeout=timeout)
    fetched = _run_git(repo, ["rev-parse", "--verify", "FETCH_HEAD^{commit}"], timeout=timeout)
    if not _GIT_REVISION.fullmatch(fetched):
        raise BackupSyncError("Git FETCH_HEAD is not a valid revision")
    info["fetched_revision"] = fetched.lower()
    return info


def _review_public(record: dict) -> dict:
    return {
        "review_id": record["review_id"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": _iso(float(record["expires_epoch"])),
        "target": record["target"],
        "remote_source": record["remote_source"],
        "candidate_hash": record["candidate_hash"],
        "remote_manifest_hash": record["remote_manifest_hash"],
        "plan": record["plan"],
        "git": record.get("git"),
        "credential_redacted": True,
    }


def _validate_review(value: object) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise BackupSyncError("sync review has an invalid header")
    review_id = value.get("review_id")
    if not isinstance(review_id, str) or not _REVIEW_ID.fullmatch(review_id):
        raise BackupSyncError("sync review id is invalid")
    if value.get("status") not in {"pending", "committed"}:
        raise BackupSyncError("sync review status is invalid")
    if not isinstance(value.get("expires_epoch"), (int, float)) or value["expires_epoch"] <= time.time():
        raise BackupSyncError("sync review has expired; prepare it again")
    for field in ("candidate_hash", "remote_manifest_hash"):
        if not isinstance(value.get(field), str) or not _HEX64.fullmatch(value[field]):
            raise BackupSyncError(f"sync review {field} is invalid")
    _target_path(value.get("target"))
    _source_label(value.get("remote_source"))
    git = value.get("git")
    if git is not None:
        if not isinstance(git, dict) or not isinstance(git.get("url"), str):
            raise BackupSyncError("sync review Git metadata is invalid")
        _source_label(git["url"])
        for revision_key in ("revision", "fetched_revision"):
            revision = git.get(revision_key)
            if revision is not None and (not isinstance(revision, str) or not _GIT_REVISION.fullmatch(revision)):
                raise BackupSyncError("sync review Git revision is invalid")
    base = _normalize_manifest(value.get("base"), "base")
    local = _normalize_manifest(value.get("local"), "local")
    remote = _normalize_manifest(value.get("remote"), "remote")
    if _manifest_digest(remote) != value["remote_manifest_hash"]:
        raise BackupSyncError("sync review remote manifest has changed")
    plan = value.get("plan")
    if not isinstance(plan, dict):
        raise BackupSyncError("sync review plan is invalid")
    strategy = plan.get("strategy")
    if three_way_plan(base, local, remote, strategy=strategy) != plan:
        raise BackupSyncError("sync review plan has changed")
    result = dict(value)
    result.update({"base": base, "local": local, "remote": remote, "plan": plan})
    _ensure_credential_free(result)
    return result


def write_sync_review(data_dir: str | Path, record: dict) -> dict:
    """Persist a bounded, private review record for a later apply transaction."""
    normalized = _validate_review(record)
    encoded = _json_bytes(normalized)
    if len(encoded) > MAX_SYNC_REVIEW_BYTES:
        raise BackupSyncError("sync review exceeds the review size limit")
    path = _review_path(data_dir, normalized["review_id"])
    directory = path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        atomic_write_text(path, encoded.decode("utf-8") + "\n")
        os.chmod(path, 0o600)
    except OSError as exc:
        raise BackupSyncError(f"could not write sync review: {exc}") from exc
    return _review_public(normalized)


def read_sync_review(data_dir: str | Path, review_id: str) -> dict:
    """Read one pending sync review without invoking Git or touching a target."""
    path = _review_path(data_dir, review_id)
    if not path.is_file() or path.is_symlink():
        raise BackupSyncError("sync review was not found")
    try:
        if path.stat().st_size > MAX_SYNC_REVIEW_BYTES:
            raise BackupSyncError("sync review exceeds the review size limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except BackupSyncError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise BackupSyncError(f"sync review is unreadable: {exc}") from exc
    result = _validate_review(value)
    if result["status"] != "pending":
        raise BackupSyncError("sync review has already been committed")
    return result


def _mark_review_committed(data_dir: str | Path, review_id: str) -> dict:
    path = _review_path(data_dir, review_id)
    value = read_sync_review(data_dir, review_id)
    value["status"] = "committed"
    value["committed_at"] = _iso()
    encoded = _json_bytes(value)
    try:
        atomic_write_text(path, encoded.decode("utf-8") + "\n")
        os.chmod(path, 0o600)
    except OSError as exc:
        raise BackupSyncError(f"could not mark sync review committed: {exc}") from exc
    return _review_public(value)


def prepare_sync_review(data_dir: str | Path, base: dict, local: dict, remote: dict, *,
                        target: dict, candidate_hash: str, strategy: str = "review",
                        git: dict | None = None) -> dict:
    """Create a private review artifact for one explicit sync candidate."""
    if not isinstance(candidate_hash, str) or not _HEX64.fullmatch(candidate_hash):
        raise BackupSyncError("candidate_hash must be a SHA-256 hex string")
    target_path = _target_path(target)
    normalized_base = _normalize_manifest(base, "base")
    normalized_local = _normalize_manifest(local, "local")
    normalized_remote = _normalize_manifest(remote, "remote")
    plan = three_way_plan(normalized_base, normalized_local, normalized_remote, strategy=strategy)
    remote_source = normalized_remote["source"]
    if git is not None:
        _ensure_credential_free(git)
        if not isinstance(git.get("url"), str):
            raise BackupSyncError("Git review metadata must contain a safe URL")
        _source_label(git["url"])
        remote_source = git["url"]
    now = time.time()
    record = {
        "version": 1,
        "review_id": hashlib.sha256(
            _json_bytes({"target": str(target_path), "candidate_hash": candidate_hash, "remote": normalized_remote})
            + str(now).encode("ascii")
        ).hexdigest()[:32],
        "status": "pending",
        "created_at": _iso(now),
        "expires_epoch": now + MAX_SYNC_REVIEW_AGE,
        "target": {"physical_path": str(target_path), "contained": True},
        "remote_source": remote_source,
        "candidate_hash": candidate_hash.lower(),
        "remote_manifest_hash": _manifest_digest(normalized_remote),
        "base": normalized_base,
        "local": normalized_local,
        "remote": normalized_remote,
        "plan": plan,
        "git": git,
    }
    return write_sync_review(data_dir, record)


def commit_sync_review(data_dir: str | Path, review_id: str, candidate: str | Path, *,
                       approve: bool = False, snapshot_root: str | Path | None = None) -> dict:
    """Apply one reviewed candidate tree through the source-lock recovery seam."""
    if approve is not True:
        raise BackupSyncError("sync apply requires explicit approve=True")
    if snapshot_root is None:
        raise BackupSyncError("snapshot_root is required before applying a sync review")
    review_path = _review_path(data_dir, review_id)
    with mutation_lock(review_path):
        review = read_sync_review(data_dir, review_id)
        target = Path(review["target"]["physical_path"]).resolve()
        candidate = Path(candidate).expanduser()
        try:
            candidate_hash = local_manifest(candidate)["sha256"]
        except (OSError, ValueError) as exc:
            raise BackupSyncError(f"sync candidate is not readable: {exc}") from exc
        if candidate_hash != review["candidate_hash"]:
            raise BackupSyncError("sync candidate changed since review")
        if review["plan"]["conflicts"]:
            raise BackupSyncError("sync review still contains unresolved conflicts")
        source_info = review.get("git") or {}
        source_kind = "git" if source_info else "local"
        source_value = source_info.get("url") if source_info else review["remote_source"]
        source = {"kind": source_kind, "value": source_value}
        if source_info.get("fetched_revision") or source_info.get("revision"):
            source["revision"] = source_info.get("fetched_revision") or source_info.get("revision")
        target_record = dict(review["target"])
        target_record.update({"exists": target.exists(), "writable": os.access(target, os.W_OK)})
        source_review = review_local_update(target, candidate, target=target_record, source=source)
        if source_review.get("review_state") != "review-required":
            raise BackupSyncError(f"sync candidate is not committable: {source_review.get('review_state')}")
        try:
            result = commit_local_update(
                target,
                candidate,
                target=target_record,
                review=source_review,
                approve=True,
                snapshot_root=snapshot_root,
                source=source,
            )
        except Exception as exc:
            if isinstance(exc, BackupSyncError):
                raise
            raise BackupSyncError(f"sync apply failed: {exc}") from exc
        committed = _mark_review_committed(data_dir, review_id)
        return {
            "committed": True,
            "review_id": review_id,
            "target": str(target),
            "snapshot": result["snapshot"],
            "source_lock": result["source_lock"],
            "review": committed,
            "credential_redacted": True,
        }


__all__ = [
    "BackupSyncError", "SYNC_REVIEW_DIRNAME", "build_manifest", "commit_sync_review",
    "dry_run", "git_fetch", "git_remote_info", "interrupted_sync", "prepare_sync_review",
    "read_sync_review", "three_way_plan", "write_sync_review",
]

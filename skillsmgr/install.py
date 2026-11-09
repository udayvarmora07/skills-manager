"""Installing skills: the ecosystem runner and the reviewed registry fetch.

Both front-ends (CLI ``install`` and ``POST /api/install``) call this module,
so the guards on every value forwarded to a runner, the argv itself, the
output policy, and the two-step registry review/commit rules exist once.
"""

from __future__ import annotations

import re
import subprocess  # nosec B404 - allowlisted runners are executed with list argv, never a shell.
import tempfile
from pathlib import Path

from .errors import StoreError
from .frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
from .registry import (
    RegistryClient,
    RegistryError,
    mark_registry_review_committed,
    materialize_snapshot,
    provenance_for_snapshot,
    read_registry_review,
    registry_reference,
    registry_review_lock,
    write_provenance,
    write_registry_review,
)
from .risk import risk_file_listing, risk_scan
from .validator import validate_skill, validate_skill_name
from .external_scan import skillspector_evidence

__all__ = [
    "INSTALL_TIMEOUT",
    "REGISTRY_PREVIEW_POLICY",
    "RUNNERS",
    "commit_registry_review",
    "install_argv",
    "install_command_line",
    "install_runner",
    "install_source",
    "install_value",
    "prepare_registry_review",
    "registry_bridge_plan",
    "registry_client",
    "registry_fetch",
    "run_install",
]

#: Each runner's prefix for the npm ``skills`` package.
RUNNERS = {
    "npx": ("npx", "skills", "add"),
    "pnpm": ("pnpm", "dlx", "skills", "add"),
    "yarn": ("yarn", "dlx", "skills", "add"),
    "bunx": ("bunx", "skills", "add"),
    "bun": ("bunx", "skills", "add"),
}
INSTALL_TIMEOUT = 120
_OUTPUT_TAIL = 8000
_MAX_INSTALL_VALUE = 256
_INSTALL_VALUE_RE = re.compile(r"[A-Za-z0-9_@./:+-]+")

REGISTRY_PREVIEW_POLICY = (
    "offline-only: no registry request, cache write, or credential use; "
    "install stays delegated to the ecosystem runner (npx skills add)"
)
_RISK_POLICY = "advisory-only; heuristic evidence is not a safety or trust verdict"


def install_runner(runner: str | None) -> str:
    """Resolve the ecosystem runner; it is an allowlist, never a shell string."""
    runner = (runner or "npx").strip() or "npx"
    if runner == "uvx":
        raise StoreError(
            "uvx does not apply to the npm 'skills' package; use npx/pnpm dlx/yarn "
            "dlx/bunx. For Python tools use pipx/uvx with a PyPI package."
        )
    if runner not in RUNNERS:
        raise StoreError(f"unsupported runner {runner!r}; use npx, pnpm, yarn, or bunx")
    return runner


def install_value(label: str, value: object) -> str:
    """Accept one value forwarded to the runner, rejecting injection shapes."""
    text = str(value).strip()
    segments = text.replace("\\", "/").split("/")
    unsafe = (
        not text
        or len(text) > _MAX_INSTALL_VALUE
        or not _INSTALL_VALUE_RE.fullmatch(text)
        or text.startswith(("-", "/", "\\"))
        or any(segment in {".", ".."} for segment in segments)
        or (len(text) >= 2 and text[1] == ":")
    )
    if unsafe:
        if label == "source":
            raise StoreError("invalid source value")
        raise StoreError(f"invalid {label} value {text!r}")
    return text


def install_source(raw: object) -> str:
    """Require a non-empty ecosystem source and validate it."""
    if raw is not None and not isinstance(raw, str):
        raise StoreError("source must be a string")
    if not (raw or "").strip():
        raise StoreError("source is required (e.g. vercel-labs/agent-skills)")
    return install_value("source", raw)


def install_argv(source: str, runner: str = "npx", scope: str = "global",
                 agents=None, skills=None, copy: bool = False,
                 list_only: bool = False) -> list[str]:
    """Render the ecosystem-runner argv for one install request."""
    parts = [*RUNNERS[install_runner(runner)], install_value("source", source)]
    if scope == "global":
        parts.append("-g")
    for label, values, flag in (("agent", agents, "-a"), ("skill", skills, "-s")):
        for value in values or []:
            parts.extend([flag, install_value(label, value)])
    if copy:
        parts.append("--copy")
    if list_only:
        parts.append("-l")
    return parts


def install_command_line(source: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False) -> str:
    """Render one install request as the printed command line."""
    return " ".join(install_argv(source, runner, scope, agents, skills, copy, list_only))


def run_install(argv: list[str]) -> dict:
    """Run a rendered argv; output is the bounded tail of each stream."""
    try:
        proc = subprocess.run(  # nosec B603 - argv comes from install_argv; shell stays false.
            argv, capture_output=True, text=True, timeout=INSTALL_TIMEOUT
        )
    except FileNotFoundError as exc:
        raise StoreError(f"runner not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        error = StoreError(f"timed out after {INSTALL_TIMEOUT}s: {exc}")
        error.status = 504
        raise error from exc
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-_OUTPUT_TAIL:],
        "stderr": proc.stderr[-_OUTPUT_TAIL:],
    }


def _offline_registry_gate(trust_requested: object, content_hash: object) -> dict:
    """Describe what an offline preview can and cannot establish.

    ``trust_confirmed`` and ``may_install`` deliberately never become true
    offline; caller intent and a supplied hash stay observable as unverified.
    """
    requested = bool(trust_requested)
    supplied_hash = isinstance(content_hash, str) and bool(content_hash)
    blockers = []
    if not requested:
        blockers.append("trust not confirmed: review source preview and "
                        "provenance, then confirm explicitly")
    blockers.append("install eligibility is unverified: offline preview did "
                    "not fetch or authenticate registry metadata")
    return {
        "may_install": False,
        "trust_confirmed": False,
        "trust_requested": requested,
        "trust_status": "unverified-offline" if requested else "not-confirmed",
        "trust_verified": False,
        "eligibility_status": "unverified-offline",
        "hash_status": "unverified-provided" if supplied_hash else "not-provided",
        "hash_verified": False,
        "blockers": blockers,
    }


def _optional_str(value: object, label: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{label} must be a string when present")
    return value


def registry_bridge_plan(spec: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False, trust_confirmed: bool = False,
                         description: str | None = None,
                         content_hash: str | None = None) -> dict:
    """Offline registry→install bridge plan (no network, no execution).

    Maps a registry reference to the command the ``install`` surface would run,
    with the audit links and hash slot used to review provenance.
    """
    reference = registry_reference(spec)
    scope = _optional_str(scope, "scope") or "global"
    content_hash = _optional_str(content_hash, "content_hash")
    targets = list(skills or []) or ([reference["slug"]] if reference["slug"] else [])
    command = install_command_line(reference["source"], runner, scope, agents,
                                   targets, copy, list_only)
    gate = _offline_registry_gate(trust_confirmed, content_hash)
    has_description = isinstance(description, str) and bool(description.strip())
    return {
        "spec": reference["spec"],
        "form": reference["form"],
        "source": reference["source"],
        "slug": reference["slug"],
        "registry_id": reference["registry_id"],
        "page_url": reference["page_url"],
        "audit_links": reference["audit_links"],
        "description": description if has_description else "",
        "description_status": "provided" if has_description else "not-provided",
        "provenance_note": "registry metadata (description, installs) needs an "
                           "authenticated catalog read; supply it manually when "
                           "you have it, otherwise provenance stays incomplete",
        "content_hash": content_hash,
        "hash_status": gate["hash_status"],
        "hash_verified": gate["hash_verified"],
        "hash_use": "compare a supplied hash only after an authenticated "
                    "registry read; this offline preview performs no comparison",
        "target_scope": scope,
        "runner": runner,
        "install_command": command,
        "steps": [
            "preview (offline): reference parsed, audit links and hash shown",
            f"dry-run: {command}",
            "record caller trust intent (still unverified offline)",
            "obtain an authenticated registry read before deciding install eligibility",
            f"run: {command} (set DISABLE_TELEMETRY=1 to opt out of runner telemetry)",
            "validate the installed copy with `validate`",
            "store the registry hash to detect later upstream change",
        ],
        "may_install": gate["may_install"],
        "trust_confirmed": gate["trust_confirmed"],
        "trust_requested": gate["trust_requested"],
        "trust_status": gate["trust_status"],
        "trust_verified": gate["trust_verified"],
        "eligibility_status": gate["eligibility_status"],
        "blockers": list(gate["blockers"]),
        "network": "deferred: no registry API request, cache, or credential is used",
        "policy": REGISTRY_PREVIEW_POLICY,
    }


def registry_client(store) -> RegistryClient:
    """The registry client bound to one Store's private cache."""
    return RegistryClient(store.data_dir)


def registry_fetch(store, *, source: object = None, review_id: object = None,
                   trust_confirmed: bool = False, scope: object = "global",
                   expected_hash: object = None, allow_stale: bool = False,
                   external_scan: dict | None = None) -> dict:
    """Run one step of the two-step registry install.

    Without ``review_id`` this fetches and inspects a snapshot (no Store
    mutation) and returns a review id.  With it, and explicit trust, the
    reviewed snapshot is committed with no further network request.
    """
    if not isinstance(scope, str) or (scope.strip() or "global") != "global":
        raise StoreError("registry fetch currently targets the global manager store only")
    if review_id is not None:
        if not isinstance(review_id, str) or not review_id.strip():
            raise StoreError("review_id must be a non-empty string")
        if not trust_confirmed:
            raise StoreError("registry commit requires trust confirmation after reviewing the fetched snapshot")
        return commit_registry_review(store, review_id.strip())
    if trust_confirmed:
        raise StoreError("fetch and trust confirmation are separate: fetch first, then commit the review id with trust confirmation")
    if expected_hash is not None and not isinstance(expected_hash, str):
        raise StoreError("registry_hash must be a string")
    return prepare_registry_review(
        store, install_source(source), expected_hash=expected_hash,
        allow_stale=allow_stale, external_scan=external_scan,
    )


def _snapshot_name(snapshot: dict) -> str:
    name = snapshot.get("slug")
    try:
        return validate_skill_name(name)
    except (TypeError, ValueError) as exc:
        raise StoreError(f"registry slug cannot be installed as a skill name: {name!r}") from exc


def _inspect_staged(name: str, staged: Path, failure: str) -> tuple:
    """Validate a staged snapshot and collect its advisory risk evidence."""
    validation = validate_skill(name, staged)
    if validation.errors:
        summary = "; ".join(issue.message for issue in validation.errors[:3])
        raise StoreError(f"{failure}: {summary}")
    findings = risk_scan({
        "name": name,
        "body": validation.body,
        "allowed_tools": validation.data.get("allowed-tools"),
        "description": validation.data.get("description"),
        "files": risk_file_listing(staged),
    })
    return validation, {"policy": _RISK_POLICY, "findings": findings}


def _normalized_snapshot(snapshot: dict, name: str) -> tuple[dict, str | None]:
    """Rename the document to the registry slug when the two disagree."""
    try:
        root_text = next(entry["contents"] for entry in snapshot["files"] if entry["path"] == "SKILL.md")
        frontmatter, body = parse_frontmatter(root_text)
    except (FrontmatterError, StopIteration):
        return snapshot, None
    remote_name = frontmatter.get("name")
    if not isinstance(remote_name, str) or remote_name == name:
        return snapshot, None
    frontmatter["name"] = name
    files = [dict(entry) for entry in snapshot["files"]]
    for entry in files:
        if entry["path"] == "SKILL.md":
            entry["contents"] = dump_frontmatter(frontmatter, key_order=list(frontmatter)) + body
    normalization = f"frontmatter.name {remote_name!r} normalized to slug {name!r}"
    local = dict(snapshot, files=files, normalization=normalization)
    local.pop("hash", None)
    return local, normalization


def _scan_externally(staged: Path, options: dict | None) -> dict | None:
    if options is None:
        return None
    return skillspector_evidence(staged, llm=options["llm"])


def prepare_registry_review(store, spec: str, *, expected_hash: str | None,
                            allow_stale: bool, external_scan: dict | None = None) -> dict:
    """Fetch and inspect a registry snapshot without touching the managed Store.

    ``external_scan`` (from ``external_scan.scan_options``) opts in to advisory
    SkillSpector evidence on the staged copy; it never changes readiness.
    """
    snapshot = registry_client(store).fetch(spec, expected_hash=expected_hash, allow_stale=allow_stale)
    name = _snapshot_name(snapshot)
    local_snapshot, normalization = _normalized_snapshot(snapshot, name)
    provenance = provenance_for_snapshot(local_snapshot)
    with tempfile.TemporaryDirectory(prefix="skillsmgr-registry-review-") as temporary:
        staged = Path(temporary) / name
        materialize_snapshot(local_snapshot, staged)
        validation, risk = _inspect_staged(name, staged, "registry snapshot failed validation before install")
        external = _scan_externally(staged, external_scan)
    inspection = {
        "validation": {
            "valid": validation.valid,
            "warnings": [
                {"level": issue.level, "key": issue.key, "message": issue.message}
                for issue in validation.warnings
            ],
        },
        "risk": risk,
        "reviewed_before_install": False,
        "review_required": True,
        "target_scope": "global",
    }
    if external is not None:
        inspection["external_scan"] = external
    local_snapshot["remote_hash"] = snapshot.get("hash")
    review = write_registry_review(store.data_dir, local_snapshot, inspection)
    registry = dict(review["registry"])
    registry["remote_hash"] = snapshot.get("hash")
    registry["remote_registry_hash"] = snapshot["registry_hash"]
    registry["registry_hash"] = provenance["registry_hash"]
    registry["snapshot_hash"] = provenance["local_snapshot_hash"]
    registry["normalization"] = normalization
    return {
        "review_id": review["review_id"],
        "review_expires_at": review["expires_at"],
        "registry": registry,
        "inspection": inspection,
    }


def commit_registry_review(store, review_id: str) -> dict:
    """Commit one registry review under the cross-process single-use lock."""
    with registry_review_lock(store.data_dir, review_id):
        return _commit_registry_review(store, review_id)


def _record_provenance(store, name: str, installed: dict, provenance: dict) -> None:
    """Write provenance into the installed skill, or undo the install."""
    try:
        write_provenance(Path(installed["path"]), provenance)
    except (RegistryError, OSError) as exc:
        store.remove(name, purge=True)
        raise StoreError(f"registry install rolled back: could not record provenance: {exc}") from exc


def _commit_registry_review(store, review_id: str) -> dict:
    """Commit one reviewed registry snapshot without another network request."""
    review = read_registry_review(store.data_dir, review_id)
    snapshot = review["snapshot"]
    name = _snapshot_name(snapshot)
    provenance = provenance_for_snapshot(snapshot)
    remote_hash = snapshot.get("remote_hash")
    if remote_hash is not None:
        provenance["remote_hash"] = remote_hash
        provenance["hash_verified"] = bool(snapshot.get("hash_verified"))
    with tempfile.TemporaryDirectory(prefix="skillsmgr-registry-commit-") as temporary:
        staged = Path(temporary) / name
        materialize_snapshot(snapshot, staged)
        _, risk = _inspect_staged(name, staged, "registry review failed validation before install")
        # Store.add strips manager sidecars from external intake (R2), so the
        # provenance this review earned is written to the installed copy.
        installed = store.add(staged, name=name)
        _record_provenance(store, name, installed, provenance)
    committed = mark_registry_review_committed(store.data_dir, review_id)
    registry = dict(committed["registry"])
    registry["remote_hash"] = remote_hash
    registry["normalization"] = snapshot.get("normalization")
    inspection = dict(review["inspection"])
    inspection.update({
        "risk": risk,
        "reviewed_before_install": True,
        "review_required": False,
        "review_id": review_id,
        "target_scope": "global",
    })
    return {
        "name": installed["name"],
        "path": installed["path"],
        "registry": registry,
        "inspection": inspection,
    }

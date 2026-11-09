"""The doctor report both front-ends show.

``store.doctor()`` audits the global Store against its index.  An agent scope
has no index, so it is audited from its filesystem tree.  ``scope=all`` adds the
per-scope summary and same-name duplicates, and ``hygiene`` adds the read-only
hygiene evidence.  The CLI and ``GET /api/doctor`` render this one report.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import scopes
from .diagnostics import diagnose as _diagnose
from .errors import StoreError
from .hygiene import hygiene_report
from .loader import scan_dir

__all__ = ["doctor_report", "hygiene_evidence", "require_scope", "scope_doctor_report"]

_MAX_REASON = 512


def require_scope(scope: str) -> None:
    """Refuse a scope id that is neither ``all`` nor a known scope."""
    if scope != "all" and scope not in {item.id for item in scopes.known_scopes()}:
        raise StoreError(f"unknown scope {scope!r}")


def scope_doctor_report(scope_id: str) -> dict:
    """Audit one agent scope directly from its filesystem tree.

    Malformed documents must stay visible here instead of being hidden behind
    ``store.doctor()``, which knows only the global tree.
    """
    scope, entries, scan_issues = _scope_doctor_scan(scope_id)

    def names(flag: str) -> list[str]:
        return sorted(str(entry["name"]) for entry in entries if entry.get(flag))

    malformed = names("malformed")
    report = {
        "scope": scope_id,
        "path": str(scope.base),
        "skills_on_disk": len(entries),
        "malformed_documents": malformed,
        "undecodable_documents": names("encoding_error"),
        "conflicting_documents": names("document_conflict"),
        "ok": not malformed,
    }
    report.update(scan_issues)
    return report


def _scope_doctor_scan(scope_id: str):
    """Keep managed peer-link reads while distinguishing an unreadable root."""
    scope = scopes.scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    degraded = []
    try:
        with os.scandir(scope.base):
            pass
    except FileNotFoundError:
        pass
    except OSError as exc:
        degraded.append({"section": "scope-scan", "reason": str(exc)[:_MAX_REASON]})
    entries = [] if degraded else scopes.scan_scope(scope_id, include_husks=True)

    issues = {"ok": False, "degraded": degraded} if degraded else {}
    return scope, entries, issues


def _add_scope_summary(report: dict) -> None:
    """Add scopes and duplicates for ``scope=all`` from one merged snapshot.

    BUG-8: a failure is reported under ``degraded`` with empty sections, so a
    client can tell "no duplicates" from "the duplicate scan crashed".
    """
    try:
        records = scopes.list_all()
        report["scopes"] = scopes.list_scopes(records=records)
        report["duplicates"] = scopes.find_duplicates(records)
    except Exception as exc:
        _diagnose("doctor scope=all enrichment failed", exc)
        report["scopes"] = []
        report["duplicates"] = []
        report.setdefault("degraded", []).append({
            "section": "scopes/duplicates",
            "reason": f"the scope and duplicate scan failed: {exc}",
        })


def _global_records(store) -> list[dict]:
    """Scan the global tree directly so unindexed husks remain evidence."""
    rows = scan_dir(store.skills_dir, include_husks=True)
    physical_root = str(store.skills_dir.resolve())
    for row in rows:
        row.update({"scope": "global", "scope_label": "Global", "consumer": "skills-manager"})
        row["path"] = row.get("path") or str(store.skills_dir / row["name"])
        row["physical_root"] = physical_root
        try:
            row["physical_path"] = str(Path(row["path"]).resolve())
        except OSError:
            row["physical_path"] = str(row["path"])
    return rows


def _hygiene_records(store, scope: str) -> tuple[list[dict], list[dict]]:
    """Observed records for the requested scope, without widening roots."""
    records: list[dict] = []
    degraded: list[dict] = []
    descriptors = [item for item in scopes.known_scopes() if scope == "all" or item.id == scope]
    for descriptor in descriptors:
        if descriptor.id != "global" and not descriptor.base.is_dir():
            continue
        try:
            records.extend(_global_records(store) if descriptor.id == "global" else scopes.scan_scope(descriptor.id))
        except Exception as exc:
            degraded.append({"section": "scope-scan", "scope": descriptor.id, "reason": str(exc)[:_MAX_REASON]})
    return records, degraded


def hygiene_evidence(store, scope: str) -> dict:
    """The read-only hygiene report for one scope (or ``all``)."""
    records, degraded = _hygiene_records(store, scope)
    try:
        result = hygiene_report(records, scope=scope)
    except Exception as exc:
        result = hygiene_report([], scope=scope)
        degraded.append({
            "section": "hygiene-report",
            "reason": "complete hygiene analysis was unavailable",
            "detail": str(exc)[:_MAX_REASON],
        })
    result["degraded"] = sorted(
        [*result["degraded"], *degraded],
        key=lambda item: (str(item.get("section", "")), str(item.get("scope", "")), str(item.get("reason", ""))),
    )
    return result


def doctor_report(store, scope: str, *, hygiene: bool = False) -> dict:
    """Compose the doctor report for ``global``, one agent scope, or ``all``."""
    require_scope(scope)
    report = store.doctor() if scope in ("global", "all") else scope_doctor_report(scope)
    if scope == "all":
        _add_scope_summary(report)
    if hygiene:
        report["hygiene"] = hygiene_evidence(store, scope)
    return report

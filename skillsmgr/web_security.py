"""Internal HTTP request-security policy helpers for the local web UI.

This module intentionally exposes a small, pure policy function.  The handler
still owns when the policy runs (before mutation routing) and the server still
owns the configured host/origin sets.
"""

from __future__ import annotations

from typing import Mapping
from urllib.parse import urlparse

from .store import StoreError


class RequestError(StoreError):
    """A clean HTTP error raised while validating an incoming request."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def validate_mutation_request(
    headers: Mapping[str, str],
    allowed_hosts: set[str],
    allowed_origins: set[str],
) -> None:
    """Validate the pre-handler policy for state-changing HTTP requests.

    Header-absent local CLI/test clients remain valid.  When browser-oriented
    headers are present, their values must match the loopback server configured
    by :class:`WebAppServer`.  This function does not inspect routes or bodies;
    callers remain responsible for JSON/content-type checks where applicable.
    """

    host_header = headers.get("Host", "")
    if host_header not in allowed_hosts:
        raise RequestError(403, "invalid Host header")

    fetch_site = (headers.get("Sec-Fetch-Site") or "").lower()
    if fetch_site == "cross-site":
        raise RequestError(403, "cross-origin request rejected")

    origin = headers.get("Origin")
    referer = headers.get("Referer")
    for value, label in ((origin, "Origin"), (referer, "Referer")):
        if not value:
            continue
        parsed = urlparse(value)
        if label == "Referer":
            actual = f"{parsed.scheme}://{parsed.netloc}"
        else:
            actual = value.rstrip("/")
        if not parsed.scheme or actual.rstrip("/") not in allowed_origins:
            raise RequestError(403, "cross-origin request rejected")

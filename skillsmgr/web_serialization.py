"""Internal JSON request/response helpers for the stdlib web backend."""

from __future__ import annotations

import json
from typing import Any

from .web_security import RequestError
from .store import StoreError


def json_bytes(obj: Any) -> bytes:
    """Serialize a response object using the existing UTF-8 JSON contract."""

    return json.dumps(obj).encode("utf-8")


def parse_json_object(raw: bytes, content_type: str) -> dict:
    """Decode an ``application/json`` body and require a JSON object.

    The status/error messages intentionally match the original handler
    implementation so callers and clients keep their existing contract.
    """

    if not (content_type.split(";", 1)[0].strip().lower() == "application/json"):
        raise RequestError(415, "JSON request body required")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise StoreError("request body is not valid JSON")
    if not isinstance(data, dict):
        raise StoreError("request body must be a JSON object")
    return data

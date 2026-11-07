"""Internal JSON request/response helpers for the stdlib web backend."""

from __future__ import annotations

import json
from typing import Any

from .web_security import RequestError
from .errors import StoreError


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
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise StoreError("request body is not valid JSON")
    if not isinstance(data, dict):
        raise StoreError("request body must be a JSON object")
    _check_json_depth(data)
    return data


def _check_json_depth(data: dict) -> None:
    """Bound nesting before downstream recursive frontmatter/metadata handling."""
    stack = [iter((data,))]
    while stack:
        try:
            value = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if isinstance(value, (dict, list)):
            if len(stack) > 64:
                raise StoreError("request JSON nesting exceeds 64 levels")
            stack.append(iter(value.values() if isinstance(value, dict) else value))

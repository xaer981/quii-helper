"""Helpers for removing secrets from debug output."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "account",
    "auth-code",
    "auth_code",
    "authorization",
    "client-id",
    "client_id",
    "cookie",
    "data-encode-key",
    "data_encode_key",
    "dynamic-password",
    "dynamic_password",
    "password",
    "set-cookie",
    "session-id",
    "session_id",
    "token",
    "transparent-basedata",
    "transparent_basedata",
}
_NORMALIZED_SENSITIVE_KEYS = {
    item.replace("_", "-") for item in _SENSITIVE_KEYS
}
_SENSITIVE_KEY_FRAGMENTS = (
    "auth",
    "cookie",
    "password",
    "secret",
    "session",
    "token",
)


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive keys replaced by a marker."""

    return {
        key: REDACTED if _is_sensitive_key(key) else value
        for key, value in values.items()
    }


def redact_xml_text(value: str) -> str:
    """Redact sensitive XML element bodies in a debug string."""

    redacted = value
    for key in _SENSITIVE_KEYS:
        tag = re.escape(key)
        redacted = re.sub(
            rf"(<{tag}\b[^>]*>)(.*?)(</{tag}>)",
            rf"\1{REDACTED}\3",
            redacted,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return redacted


def redact_json_text(value: str) -> str:
    """Redact sensitive JSON object values in a debug string."""

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return json.dumps(_redact_json_value(parsed), ensure_ascii=False)


def _redact_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: (
                REDACTED
                if _is_sensitive_key(str(key))
                else _redact_json_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("_", "-")
    return normalized in _NORMALIZED_SENSITIVE_KEYS or any(
        fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS
    )

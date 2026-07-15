"""JSON request builders for the local device `/tdkcgi` endpoint."""

from __future__ import annotations

import json
from typing import Any


def build_common_json_request(
    command: str,
    *,
    security: str,
    username: str,
    password: str,
    passwordencode: int = 1,
    content: dict[str, Any] | None = None,
) -> bytes:
    """Build the native common JSON CGI request envelope."""

    body: dict[str, Any] = {"command": command}
    if content is not None:
        body["content"] = content

    payload: dict[str, Any] = {
        "body": body,
        "header": {
            "security": security,
            "username": username,
            "password": password,
            "passwordencode": passwordencode,
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")

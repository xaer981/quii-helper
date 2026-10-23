from typing import Any

from quii_helper.device.cgi.client import COMMAND_GET_STREAM_KEY_INFO
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_stream_key_info,
)
from quii_helper.device.http.transport import request_cgi
from quii_helper.device.security.auth import encode_device_password
from quii_helper.support.errors import ConfigurationError


def validate_stream_credentials(stream_key: str, auth_code: str) -> None:
    """Check the supported LAN key/auth pair without I/O or exposing values."""
    if not isinstance(stream_key, str):
        raise ConfigurationError("STREAM_KEY must be a string")
    try:
        key = stream_key.encode("utf-8")
    except UnicodeError:
        raise ConfigurationError(
            "STREAM_KEY must contain valid UTF-8"
        ) from None
    if len(key) != 32 or "\x00" in stream_key:
        raise ConfigurationError(
            "STREAM_KEY must contain exactly 32 UTF-8 bytes"
        )
    if not isinstance(auth_code, str) or not auth_code:
        raise ConfigurationError("LAN playback requires a nonempty AUTH_CODE")
    try:
        encoded_auth = encode_device_password(auth_code)
        encoded_auth.encode("utf-8")
    except UnicodeError:
        raise ConfigurationError(
            "AUTH_CODE must contain valid UTF-8"
        ) from None
    if any(c in encoded_auth for c in ("\x00", "&")):
        raise ConfigurationError("LAN playback requires a valid AUTH_CODE")


def request_streamkey(**kwargs: Any) -> dict[str, str]:
    result = request_cgi(COMMAND_GET_STREAM_KEY_INFO, **kwargs)
    if result["error"] != "0":
        raise RuntimeError(f"device error: {result['error']}")

    info = parse_stream_key_info(
        parse_cgi_response(COMMAND_GET_STREAM_KEY_INFO, result["raw"])
    )
    return {
        "key": info.key,
        "tdc": info.tdc,
        "synctime": info.sync_time,
    }

"""Explicit local device control commands, separate from read-only probes."""

import http.client
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from quii_helper.device.cgi.client import DEFAULT_CGI_USERNAME
from quii_helper.device.http.transport import request_cgi
from quii_helper.device.security.auth import encode_device_password
from quii_helper.support.error_codes import describe_error_code
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

COMMAND_OPEN_DOOR = "set.device.opendoor"
UnlockPasswordMode = Literal["auto", "plain", "sha256"]


@dataclass(frozen=True)
class CameraDoorOpenResult:
    """Device acknowledgement of a door-opening command.

    Attributes:
        error: Raw device command result code; zero means accepted.
        channel: Requested video-panel channel (`door` in the native XML).
        lock_number: Requested lock/relay number (`locknumber` in native XML).

    An accepted command does not confirm physical door movement.
    """

    error: int
    channel: int
    lock_number: int

    @property
    def accepted(self) -> bool:
        """Whether the device explicitly acknowledged the command as successful."""
        return self.error == 0

    @property
    def message(self) -> str:
        """Return acknowledgement text or the native unlock error description."""
        if self.accepted:
            return "Door-open command accepted by device"
        return describe_error_code(self.error, domain="device_unlock")


def request_open_door(
    *,
    host: str,
    auth_code: str,
    unlock_password: str,
    channel: int,
    lock_number: int,
    password_mode: UnlockPasswordMode = "auto",
    supports_sha256_password: bool | None = None,
    port: int = 80,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> CameraDoorOpenResult:
    """Send one native-compatible XML unlock command, without retry or redirect.

    The body password is encoded only when capability 24 or the explicit mode
    selects SHA-256. The CGI header always uses encoded `auth_code`.
    Transport or malformed-response failures leave the physical outcome unknown
    and raise `QuiiConnectionError`; they never trigger another command.
    """
    for name, value in (
        ("channel", channel),
        ("lock_number", lock_number),
        ("port", port),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigurationError(f"{name} must be a positive integer")
    if port > 65535:
        raise ConfigurationError("port must be between 1 and 65535")
    if scheme not in {"http", "https"}:
        raise ConfigurationError("scheme must be http or https")
    if not host.strip():
        raise ConfigurationError(
            "CAMERA_DEVICE_HOST is required to open a door"
        )
    if not auth_code.strip():
        raise ConfigurationError("AUTH_CODE is required to open a door")
    if not unlock_password.strip():
        raise ConfigurationError(
            "UNLOCK_PASSWORD is required to open a door; set it in .env "
            "or pass unlock_password=..."
        )
    if password_mode not in {"auto", "plain", "sha256"}:
        raise ConfigurationError(
            "password_mode must be auto, plain, or sha256"
        )
    if password_mode == "auto" and supports_sha256_password is None:
        raise ConfigurationError(
            "Device SHA-256 password capability (24) is unknown; pass "
            "password_mode='plain' or password_mode='sha256' explicitly. "
            "No door-open command was sent."
        )
    encode_password = password_mode == "sha256" or (
        password_mode == "auto" and supports_sha256_password is True
    )

    content = ET.Element(
        "content",
        {"class": "com.quvii.qvweb.device.bean.requset.DeviceUnlockContent"},
    )
    ET.SubElement(content, "door").text = str(channel)
    ET.SubElement(content, "locknumber").text = str(lock_number)
    ET.SubElement(content, "password").text = (
        encode_device_password(unlock_password)
        if encode_password
        else unlock_password
    )
    try:
        response = request_cgi(
            COMMAND_OPEN_DOOR,
            host=host,
            port=port,
            username=DEFAULT_CGI_USERNAME,
            password=encode_device_password(auth_code),
            encrypted=False,
            scheme=scheme,
            passwordencode="1",
            content=content,
            verify_tls=verify_tls,
            debug=debug,
            allow_redirects=False,
        )
        root = ET.fromstring(response["raw"])
        errors = root.findall("./body/error")
        if (
            root.tag != "envelope"
            or len(root.findall("./body")) != 1
            or len(errors) != 1
            or len(errors[0]) != 0
        ):
            raise ValueError("expected one envelope/body/error element")
        error_text = (errors[0].text or "").strip()
        if re.fullmatch(r"[+-]?[0-9]+", error_text) is None:
            raise ValueError("expected an integer error code")
        error = int(error_text)
    except (
        OSError,
        http.client.HTTPException,
        ET.ParseError,
        ValueError,
        RuntimeError,
    ) as exc:
        raise QuiiConnectionError(
            "Door-open request was not confirmed; the device may have acted. "
            "The command was not retried."
        ) from exc
    return CameraDoorOpenResult(
        error=error, channel=channel, lock_number=lock_number
    )

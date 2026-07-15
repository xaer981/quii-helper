import json
import ssl
import urllib.error
import urllib.request
from typing import Any, cast

from quii_helper.cloud.iot.models import CameraIotCommandSupportInfo
from quii_helper.cloud.iot.parser import (
    COMMAND_GET_RPC_COMMAND_LIST,
    parse_iot_command_support,
)
from quii_helper.support.errors import QuiiConnectionError

IOT_SYNC_CONTROL_PATH = "/openapi-tdk/devctr/synccontrol/singledev"


def build_iot_control_payload(
    device_id: str,
    *,
    password: str,
    command: str,
    content: object | None = None,
    sub_device_code: str | None = None,
) -> dict[str, object]:
    """Build native-compatible `QvBaseIotControl.createRequestContent` body."""

    payload: dict[str, object] = {
        "deviceId": device_id,
        "password": password,
        "command": command,
        "content": content if content is not None else {},
    }
    if sub_device_code:
        payload["subDevCode"] = sub_device_code
    return payload


def request_iot_command_support(
    base_url: str,
    *,
    token: str,
    device_id: str,
    password: str,
    timeout: float,
    verify_tls: bool,
) -> CameraIotCommandSupportInfo:
    """Request read-only IoT/RRPC command support from the cloud service."""

    url = f"{base_url.rstrip('/')}{IOT_SYNC_CONTROL_PATH}"
    data = json.dumps(
        build_iot_control_payload(
            device_id,
            password=password,
            command=COMMAND_GET_RPC_COMMAND_LIST,
        ),
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "okhttp/3.12.13",
            "token": token,
        },
    )
    context = (
        ssl.create_default_context()
        if verify_tls
        else ssl._create_unverified_context()
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=context
        ) as response:
            response_bytes = cast(bytes, response.read())
    except urllib.error.URLError as exc:
        raise QuiiConnectionError(
            f"IoT command support request failed: {exc}"
        ) from exc

    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise QuiiConnectionError(
            "IoT command support response is not JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise QuiiConnectionError(
            "IoT command support response is not an object"
        )
    info = parse_iot_command_support(cast(dict[str, Any], payload))
    if info.result != 0:
        raise QuiiConnectionError(f"IoT command support result: {info.result}")
    return info

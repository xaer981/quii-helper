import json
import ssl
import urllib.error
import urllib.request
from typing import Any, cast

from quii_helper.cloud.shadow.models import CameraDeviceShadowInfo
from quii_helper.cloud.shadow.parser import parse_device_shadow_info
from quii_helper.support.errors import QuiiConnectionError

SHADOW_FIELD_DEVICE_STATE = "Device_state"
SHADOW_STATUS_PATH = "/openapi-tdk/device/status"


def build_shadow_status_payload(
    thing_id: str,
    *,
    fields: tuple[str, ...] = (SHADOW_FIELD_DEVICE_STATE,),
) -> dict[str, object]:
    """Build the native `QvDeviceFieldInfo` JSON body."""

    return {"thingId": thing_id, "fieldNames": list(fields)}


def request_device_shadow_info(
    base_url: str,
    *,
    token: str,
    thing_id: str,
    timeout: float,
    verify_tls: bool,
) -> CameraDeviceShadowInfo:
    """Request read-only device shadow status from the cloud OpenAPI service."""

    url = f"{base_url.rstrip('/')}{SHADOW_STATUS_PATH}"
    data = json.dumps(
        build_shadow_status_payload(thing_id),
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
            f"cloud shadow request failed: {exc}"
        ) from exc

    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise QuiiConnectionError("cloud shadow response is not JSON") from exc

    if not isinstance(payload, dict):
        raise QuiiConnectionError("cloud shadow response is not an object")
    return parse_device_shadow_info(cast(dict[str, Any], payload))

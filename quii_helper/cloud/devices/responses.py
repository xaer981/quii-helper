import xml.etree.ElementTree as ET

from quii_helper.cloud.devices.models import CloudDeviceListEntry
from quii_helper.support.errors import QuiiConnectionError


def parse_device_list_response(
    root: ET.Element,
) -> tuple[list[CloudDeviceListEntry], int | None]:
    """Parse cloud `get-device-list` response entries and total count."""

    header = root.find("./header")
    if header is None:
        raise QuiiConnectionError("device-list response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise QuiiConnectionError(f"device-list result: {result}")

    content = root.find("./content")
    if content is None:
        raise QuiiConnectionError("device-list response content not found")

    devices = content.findall("device") or content.findall(".//device")
    return (
        [_parse_device(device) for device in devices],
        _optional_int(content.findtext("count")),
    )


def _parse_device(device: ET.Element) -> CloudDeviceListEntry:
    return CloudDeviceListEntry(
        device_id=_text(device, "id", "device-id", "deviceid"),
        name=_text(device, "name"),
        memo_name=_text(device, "memo-name"),
        channel_count=_optional_int(_text(device, "channel-num")),
        device_type=_text(device, "type"),
        model=_text(device, "model"),
        is_hs_device=_optional_bool(_text(device, "is-hs-device")),
        from_share=_optional_bool(_text(device, "from-share")),
        share_mode=_text(device, "share-mode"),
        password_expired=_optional_bool(_text(device, "password-expired")),
        transparent_basedata=_text(device, "transparent-basedata"),
    )


def _text(element: ET.Element, *names: str) -> str:
    for name in names:
        value = element.findtext(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


def _optional_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _optional_bool(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None

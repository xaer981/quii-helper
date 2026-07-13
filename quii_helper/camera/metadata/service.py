from quii_helper.camera.metadata.models import CameraDeviceInfo
from quii_helper.cloud.devices import CloudDeviceListEntry
from quii_helper.config import AutonomousConfig, RuntimeCredentials


def camera_device_info_from_credentials(
    config: AutonomousConfig,
    credentials: RuntimeCredentials,
    *,
    cloud_device: CloudDeviceListEntry | None = None,
) -> CameraDeviceInfo:
    """Build safe read-only metadata from cloud runtime credentials."""

    token = credentials.raw.get("token", {})
    return CameraDeviceInfo(
        device_id=_first_non_empty(
            _device_value(cloud_device, "device_id"),
            token.get("device_id"),
            config.device_id,
        ),
        channel_count=_first_optional_int(
            _device_value(cloud_device, "channel_count"),
            token.get("channel_num"),
        ),
        device_type=_first_non_empty(
            _device_value(cloud_device, "device_type"),
            token.get("device_type"),
        ),
        model=_first_non_empty(
            _device_value(cloud_device, "model"),
            token.get("model"),
        ),
        is_hs_device=_first_optional_bool(
            _device_value(cloud_device, "is_hs_device"),
            _optional_bool(token.get("is_hs_device")),
        ),
        from_share=_first_optional_bool(
            _device_value(cloud_device, "from_share"),
            _optional_bool(token.get("from_share")),
        ),
        share_mode=_first_non_empty(
            _device_value(cloud_device, "share_mode"),
            token.get("share_mode"),
        ),
        password_expired=_first_optional_bool(
            _device_value(cloud_device, "password_expired"),
            _optional_bool(token.get("pwd_expired")),
        ),
        transparent_basedata=_first_non_empty(
            _device_value(cloud_device, "transparent_basedata"),
            credentials.transparent_basedata,
        ),
        name=_first_non_empty(_device_value(cloud_device, "name")),
        memo_name=_first_non_empty(_device_value(cloud_device, "memo_name")),
    )


def _device_value(
    device: CloudDeviceListEntry | None,
    name: str,
) -> object | None:
    return getattr(device, name) if device is not None else None


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _first_optional_bool(*values: object) -> bool | None:
    for value in values:
        if value is not None:
            return bool(value)
    return None


def _first_optional_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        converted = _optional_int(value)
        if converted is not None:
            return converted
    return None


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

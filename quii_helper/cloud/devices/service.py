from quii_helper.cloud.devices.models import CloudDeviceListEntry
from quii_helper.cloud.devices.requests import build_device_list_xml
from quii_helper.cloud.devices.responses import parse_device_list_response
from quii_helper.cloud.http.transport import request_userauth
from quii_helper.config import AutonomousConfig


def fetch_cloud_device_list(
    config: AutonomousConfig,
    *,
    session_id: str,
    page_size: int = 50,
    max_pages: int = 10,
) -> list[CloudDeviceListEntry]:
    """Fetch cloud device-list entries for the logged-in account."""

    devices: list[CloudDeviceListEntry] = []
    for page in range(max_pages):
        root, _raw = request_userauth(
            build_device_list_xml(
                config,
                session_id=session_id,
                count=page_size,
                page=page,
            ),
            auth_url=config.auth_url,
            verify_tls=config.tls_verify,
        )
        page_devices, total_count = parse_device_list_response(root)
        devices.extend(page_devices)
        if _is_last_page(
            page_devices=page_devices,
            page_size=page_size,
            devices_seen=len(devices),
            total_count=total_count,
        ):
            break
    return devices


def find_cloud_device(
    devices: list[CloudDeviceListEntry],
    device_id: str,
) -> CloudDeviceListEntry | None:
    """Return the cloud list entry matching `device_id`, if present."""

    for device in devices:
        if device.device_id == device_id:
            return device
    return None


def _is_last_page(
    *,
    page_devices: list[CloudDeviceListEntry],
    page_size: int,
    devices_seen: int,
    total_count: int | None,
) -> bool:
    if not page_devices or len(page_devices) < page_size:
        return True
    if total_count is not None and total_count > 0:
        return devices_seen >= total_count
    return False

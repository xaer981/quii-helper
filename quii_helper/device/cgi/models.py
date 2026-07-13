"""Typed models for read-only device CGI responses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceCgiResponse:
    """Raw parsed `/tdkcgi` response.

    Attributes:
        command: Requested CGI command.
        error: Numeric device error code from `body/error`.
        content: Parsed `body/content` XML tree as nested dictionaries/lists.
        raw_xml: Original XML response text.
    """

    command: str
    error: int
    content: dict[str, Any]
    raw_xml: str


@dataclass(frozen=True)
class DeviceStorageDisk:
    """One storage disk/card entry reported by `get.hdd.base`."""

    exists: bool
    disk_id: str
    status: str
    name: str = ""
    attributes: str = ""
    type: str = ""
    total: int | None = None
    free: int | None = None
    group_id: str = ""


@dataclass(frozen=True)
class DeviceStorageInfo:
    """Storage summary reported by `get.hdd.base`.

    The original app maps this command to `QvDeviceStorageInfo`.
    """

    error: int
    total_sum: int | None
    free_sum: int | None
    disks: list[DeviceStorageDisk] = field(default_factory=list)
    mode: str = ""
    group_max: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLanInfo:
    """One LAN interface reported inside `get.network.config`."""

    name: str = ""
    ip_address: str = ""
    subnet_mask: str = ""
    gateway: str = ""
    mac: str = ""
    dhcp: bool | None = None


@dataclass(frozen=True)
class DeviceNetworkInfo:
    """Network configuration reported by `get.network.config`.

    The original app maps the top-level `network` element into `QvDevice`
    fields, and may additionally use the first `lanlist/lan` entry.
    """

    error: int
    address: str = ""
    subnet_mask: str = ""
    gateway: str = ""
    dhcp: bool | None = None
    lan_interfaces: list[DeviceLanInfo] = field(default_factory=list)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAllInfo:
    """Broad device status returned by `get.device.status`.

    This CGI response is intentionally broad and firmware-dependent. Stable
    high-value fields are exposed directly; the full parsed content remains in
    `content` for callers that need vendor-specific details.
    """

    error: int
    model: str = ""
    version: str = ""
    release_date: str = ""
    latest_version: str = ""
    latest_release_date: str = ""
    mac: str = ""
    ssid: str = ""
    rssi: int | None = None
    time_zone: str = ""
    total_sum: int | None = None
    free_sum: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None

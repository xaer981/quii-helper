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
class DeviceProductInfo:
    """Product identity reported by `get.product.info`.

    The original app maps this command into `QvDeviceInfo`.
    """

    error: int
    mac: str = ""
    version: str = ""
    release_date: str = ""
    model: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceTimeInfo:
    """Device time and timezone reported by `get.product.time`."""

    error: int
    time_zone: str = ""
    date_time: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceWifiNetwork:
    """One Wi-Fi network entry reported by `get.wifi.list`."""

    network_id: str = ""
    ssid: str = ""
    rssi: int | None = None
    is_encrypted: bool | None = None


@dataclass(frozen=True)
class DeviceWifiListInfo:
    """Available Wi-Fi networks reported by `get.wifi.list`."""

    error: int
    networks: list[DeviceWifiNetwork] = field(default_factory=list)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceScreenFlipInfo:
    """Screen flip state reported by `get.shape.mirror`.

    `state` and `angle` follow the original app's `QvDeviceScreenFlipState`
    mapping. Raw string values are preserved for firmware-specific callers.
    """

    error: int
    mirror: str = ""
    rotate: str = ""
    state: int = 0
    angle: int = 0
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceVideoSwitchInfo:
    """Video on/off state reported by `get.videoswitch.vionoff`."""

    error: int
    value: str = ""
    state: int = 0
    is_on: bool = False
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceTimeTitleOverlay:
    """One time-title overlay geometry entry from `get.video.timetitle`."""

    stream_type: int | None = None
    video_width: int | None = None
    video_height: int | None = None
    title_width: int | None = None
    title_height: int | None = None
    location_x: int | None = None
    location_y: int | None = None


@dataclass(frozen=True)
class DeviceTimeTitleInfo:
    """Time-title overlay geometry reported by `get.video.timetitle`."""

    error: int
    overlays: list[DeviceTimeTitleOverlay] = field(default_factory=list)
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
class DeviceGeneralInfo:
    """General system settings reported by `get.system.general`.

    This is a read-only view of the original app's
    `QvDeviceGeneralSettingInfo` mapping.
    """

    error: int
    language: str = ""
    auto_sync_time: bool | None = None
    time_zone: str = ""
    date_time: str = ""
    device_id: str = ""
    host_name: str = ""
    date_split: str = ""
    date_format: str = ""
    time_format: str = ""
    on_storage_full: str = ""
    video_standard: str = ""
    auto_logout: int | None = None
    startup_wizard: bool | None = None
    smart_display: bool | None = None
    smart_tracking: bool | None = None
    preview_strategy: str = ""
    support_host_name: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceCapabilitiesInfo:
    """Device capabilities reported by `get.system.ability`.

    Capability values are kept as integers because firmware builds may use
    bitmasks instead of strict booleans.
    """

    error: int
    wifi: int | None = None
    rtsp: int | None = None
    snap: int | None = None
    talk: int | None = None
    ptz: int | None = None
    ptz_preset: int | None = None
    https: int | None = None
    ntp: int | None = None
    cloud: int | None = None
    cloud_storage: int | None = None
    cloud_upgrade: int | None = None
    automatic_ip: int | None = None
    motion_detection: int | None = None
    alarm_in: int | None = None
    video_lost: int | None = None
    video_shelter: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceVideoStreamInfo:
    """One encode stream entry reported by `get.encode`."""

    name: str
    enabled: bool | None = None
    compression: str = ""
    resolution: str = ""
    bitrate: int | None = None
    bitrate_control: str = ""
    fps: int | None = None
    gop: int | None = None
    quality: int | None = None
    audio_enabled: bool | None = None
    h264plus_enabled: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceVideoChannelInfo:
    """One video channel reported by `get.encode`."""

    channel_id: str = ""
    name: str = ""
    ability: str = ""
    encode_new: bool | None = None
    video_mode: str = ""
    protocol: str = ""
    streams: list[DeviceVideoStreamInfo] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceVideoConfigInfo:
    """Video encode configuration reported by `get.encode`.

    This method is read-only in this project and mirrors the original app's
    full-channel `getVideoConfigInfo` request.
    """

    error: int
    channels: list[DeviceVideoChannelInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
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

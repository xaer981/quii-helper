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


TF_CARD_STATUS_UNKNOWN = -1
TF_CARD_STATUS_NOT_FORMATTED = 1
TF_CARD_STATUS_ERROR = 2
TF_CARD_STATUS_SLEEP = 3
TF_CARD_STATUS_NORMAL = 4
TF_CARD_STATUS_NO_DISK = 5


@dataclass(frozen=True)
class DeviceTfCardDiskInfo:
    """One TF-card disk entry reported by `get.tfcard.info`.

    `status` follows the original app's `QvDeviceTfCardInfo` constants and
    `status_raw` preserves the firmware string for unsupported variants.
    """

    exists: bool
    disk_id: int | None = None
    status: int = TF_CARD_STATUS_UNKNOWN
    status_raw: str = ""
    total: int | None = None
    free: int | None = None


@dataclass(frozen=True)
class DeviceTfCardInfo:
    """TF-card status reported by `get.tfcard.info`.

    This mirrors the original app's `TfCardInfoResp` mapping into
    `QvDeviceTfCardInfo`.
    """

    error: int
    formatting: bool | None = None
    total_sum: int | None = None
    free_sum: int | None = None
    disks: list[DeviceTfCardDiskInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
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
class DeviceStreamKeyInfo:
    """Stream key metadata reported by `get.device.streamkey`."""

    error: int
    key: str = ""
    tdc: str = ""
    sync_time: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceQrCodeInfo:
    """Device QR code reported by `get.device.qrcode`.

    The original app exposes this command as a nullable string. This model
    keeps the device error code as well, so callers can distinguish an empty
    QR value from a failed request.
    """

    error: int
    qr_code: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceRecordScheduleTime:
    """One `time1`...`time6` record schedule entry.

    `record_type`, `start`, and `end` mirror the original app's
    `QvScheduleTimeInfo(type, start, end)` fields.
    """

    slot: int
    record_type: str = ""
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DeviceRecordConfigInfo:
    """Record configuration reported by `get.record.config`.

    This mirrors the original app's `QvDeviceRecordConfigInfo` mapping while
    keeping the weekly schedule in a Python-friendly `day -> entries` mapping.
    """

    error: int
    channel_id: int | None = None
    record_stream: str = ""
    prerecord: int | None = None
    redundancy: bool | None = None
    packet_length: int | None = None
    record_control: str = ""
    schedule: dict[str, list[DeviceRecordScheduleTime]] = field(
        default_factory=dict
    )
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceRecordSessionInfo:
    """Archive search session reported by `get.record.session`.

    The original app uses this id as the input for subsequent
    `get.record.message` calls that stream the actual record list.
    """

    error: int
    session_id: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceRecordFileInfo:
    """One archive file entry returned by `get.record.message`.

    The firmware response is parsed by the original app with a custom pull
    parser, not a SimpleXML response class. Stable, commonly observed fields
    are exposed directly and the full parsed record dictionary is preserved in
    `raw`.
    """

    record_id: str = ""
    file_name: str = ""
    file_type: str = ""
    occur_type: str = ""
    channel_id: str = ""
    start_time: str = ""
    end_time: str = ""
    stream: str = ""
    file_size: int | None = None
    url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceRecordMessageInfo:
    """Archive record list page returned by `get.record.message`.

    `result` preserves the native paging/status value when firmware provides
    it. The original client keeps requesting `get.record.message` until that
    value becomes `0`.
    """

    error: int
    records: list[DeviceRecordFileInfo] = field(default_factory=list)
    result: int | None = None
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceRecordListInfo:
    """Aggregated archive record list from the native read-only CGI flow.

    The original app first opens a `get.record.session` search and then keeps
    requesting `get.record.message` pages until the native paging `result`
    becomes `0`.
    """

    error: int
    session_id: str = ""
    records: list[DeviceRecordFileInfo] = field(default_factory=list)
    pages: list[DeviceRecordMessageInfo] = field(default_factory=list)
    completed: bool = False
    session: DeviceRecordSessionInfo | None = None


@dataclass(frozen=True)
class DeviceRecordAlarmInfo:
    """Alarm-linked archive records returned by `get.record.alarmrecord`.

    The original app sends one timestamp plus optional alarm identifiers, then
    parses the response with the same record-list parser used for archive pages.
    """

    error: int
    records: list[DeviceRecordFileInfo] = field(default_factory=list)
    result: int | None = None
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmChannel:
    """One alarm channel returned by `get.encode.channelname`."""

    channel_id: int | None = None
    name: str = ""
    channel_type: str = ""
    serial_no: int | None = None


@dataclass(frozen=True)
class DeviceAlarmChannelInfo:
    """Alarm channel list returned by `get.encode.channelname`."""

    error: int
    channels: list[DeviceAlarmChannel] = field(default_factory=list)
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
class DeviceAttachmentProfile:
    """Sub-device profile reported by `get.device.attachInfo`.

    The original app maps `channelinfo` into `QvDeviceAttachmentInfo.Profile`.
    """

    total_channel_num: int | None = None
    cam_num: int | None = None
    cctv_num: int | None = None
    ipg_num: int | None = None
    manage_num: int | None = None
    ep_num: int | None = None
    switch_direct: bool | None = None


@dataclass(frozen=True)
class DeviceAttachmentLock:
    """One channel lock entry reported by `get.device.attachInfo`."""

    lock_id: int | None = None
    name: str = ""
    enabled: bool | None = None


@dataclass(frozen=True)
class DeviceAttachmentChannel:
    """One attached channel reported by `get.device.attachInfo`."""

    channel_id: int | None = None
    name: str = ""
    channel_type: str = ""
    sub_type: int = 0
    enabled: bool | None = None
    video_enabled: bool | None = None
    talk_enabled: bool | None = None
    cctv_type: int | None = None
    locks: list[DeviceAttachmentLock] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAttachmentElevator:
    """One elevator attachment reported by `get.device.attachInfo`."""

    elevator_id: int | None = None
    enabled: bool | None = None


@dataclass(frozen=True)
class DeviceAttachmentAlarm:
    """Alarm attachment state reported by `get.device.attachInfo`."""

    enabled: bool | None = None
    mode: int | None = None
    numbers: int | None = None
    arming_type: int = 3


@dataclass(frozen=True)
class DeviceAttachmentSmartSwitch:
    """Smart switch attachment state reported by `get.device.attachInfo`."""

    enabled: bool | None = None
    room: int | None = None
    total: int | None = None


@dataclass(frozen=True)
class DeviceAttachmentInfo:
    """Sub-device attachment information from `get.device.attachInfo`.

    This mirrors the original app's XML `GetDeviceAttachmentResp` mapping into
    `QvDeviceAttachmentInfo` and keeps raw parsed content for vendor-specific
    fields.
    """

    error: int
    profile: DeviceAttachmentProfile | None = None
    channels: list[DeviceAttachmentChannel] = field(default_factory=list)
    elevators: list[DeviceAttachmentElevator] = field(default_factory=list)
    alarms: list[DeviceAttachmentAlarm] = field(default_factory=list)
    smart_switches: list[DeviceAttachmentSmartSwitch] = field(
        default_factory=list
    )
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceMotionDetectionInfo:
    """Motion detection state reported by `get.motiondetection.info`.

    The original app maps this command into `QvDeviceMotionDetectionInfo`.
    """

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    sensitivity: int | None = None
    range: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmMotionDetectionInfo:
    """Alarm motion-detection state reported by `get.alarm.motiondetection`.

    The original app maps this command into `QvAlarmMotionDetectionVInfo`.
    """

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    sensitivity: int | None = None
    peds_enabled: int | None = None
    row_num: int | None = None
    col_num: int | None = None
    region_data: list[str] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmVideoLostInfo:
    """Video-lost alarm state reported by `get.alarm.videolost`."""

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmVideoShelterInfo:
    """Video-shelter alarm state reported by `get.alarm.videoshelter`."""

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    sensitivity: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmInputChannel:
    """One alarm input channel returned by `get.alarm.alarmin`."""

    channel_id: int | None = None
    enabled: bool | None = None
    input_type: str = ""
    name: str = ""


@dataclass(frozen=True)
class DeviceAlarmInputInfo:
    """Alarm input channel list returned by `get.alarm.alarmin`."""

    error: int
    channels: list[DeviceAlarmInputChannel] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmScheduleSlot:
    """One alarm schedule time slot from `get.alarm.*.schedule`."""

    slot: int
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DeviceAlarmScheduleDay:
    """One weekday schedule from `get.alarm.*.schedule`."""

    day: str
    slots: list[DeviceAlarmScheduleSlot] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmScheduleInfo:
    """Alarm schedule returned by one `get.alarm.*.schedule` command."""

    error: int
    alarm_type: str = ""
    channel_id: int | None = None
    days: dict[str, DeviceAlarmScheduleDay] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceHumanTraceInfo:
    """Human-trace state reported by `get.humantrace.info`."""

    error: int
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceMoveDetectionInfo:
    """Move-detection state reported by `get.movedetection.info`."""

    error: int
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DevicePtzStateInfo:
    """Pan/tilt position reported by `get.ptz.position`.

    The original app maps this response into `QvDevicePanTiltControlState`.
    """

    error: int
    position_x: int | None = None
    position_y: int | None = None
    min_x: int | None = None
    max_x: int | None = None
    min_y: int | None = None
    max_y: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DevicePtzPreset:
    """One PTZ preset reported by `get.ptz.preset`."""

    preset_id: str = ""
    name: str = ""


@dataclass(frozen=True)
class DevicePtzPresetInfo:
    """PTZ preset list reported by `get.ptz.preset`."""

    error: int
    presets: list[DevicePtzPreset] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceUpgradeVersionInfo:
    """Latest firmware version reported by `get.system.upgradeversion`.

    The original app maps this response into `QvDeviceLatestVersionInfo`.
    """

    error: int
    version: str = ""
    release_time: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceUpgradeStatusInfo:
    """Firmware upgrade status reported by `get.system.upgradestatus`.

    `status` follows the original app's `QvDeviceUpgradeStatusInfo` constants.
    """

    error: int
    status: int | None = None
    version: str = ""
    time: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceUpgradeProcessInfo:
    """Firmware upgrade progress reported by `get.system.upgradeprocess`."""

    error: int
    process: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFpsChannelInfo:
    """One channel/stream FPS entry reported by `get.encode.fps`."""

    channel_id: int
    stream_id: int
    fps: int


@dataclass(frozen=True)
class DeviceFpsInfo:
    """FPS values reported by `get.encode.fps`.

    The original app maps this command into `QvDeviceFpsInfo`.
    """

    error: int
    channels: list[DeviceFpsChannelInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSmartLightItem:
    """One smart-light entry reported by `get.smart.lightinfo`."""

    light_no: int | None = None
    name: str = ""
    state: int | None = None


@dataclass(frozen=True)
class DeviceSmartLightInfo:
    """Smart-light room state reported by `get.smart.lightinfo`.

    The original app maps this command into `QvDeviceSmartLightInfo`.
    """

    error: int
    room: int | None = None
    light_num: int | None = None
    lights: list[DeviceSmartLightItem] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSoundLightChannelInfo:
    """One channel entry reported by `get.soundandlight.state`."""

    channel_id: str = ""
    ctrl_state: int | None = None


@dataclass(frozen=True)
class DeviceSoundLightInfo:
    """Sound-and-light one-key control state.

    The original app maps this command into `QvDeviceSoundLightControlInfo`.
    """

    error: int
    channels: list[DeviceSoundLightChannelInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
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
    network_type: str = ""
    supported_network_types: str = ""


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
class DeviceNetworkBaseAbility:
    """Network-base capability flags reported by `get.network.base`."""

    valid: int | None = None
    support_dhcp: int | None = None
    support_inner_ip: int | None = None
    support_multi_eth: int | None = None


@dataclass(frozen=True)
class DeviceNetworkTransferPolicy:
    """Transfer policy value reported by `get.network.base`."""

    value: str = ""
    supported: str = ""


@dataclass(frozen=True)
class DeviceNetworkBaseInfo:
    """Extended network base settings reported by `get.network.base`.

    The original app requests this command for VSU devices and maps the
    response from `GetNetworkBaseResp`.
    """

    error: int
    dns: str = ""
    secondary_dns: str = ""
    http_port: int | None = None
    media_port: int | None = None
    rtsp_port: int | None = None
    rtsp_url: str = ""
    handset_port: int | None = None
    max_users: int | None = None
    transfer_mode: bool | None = None
    hs_download: bool | None = None
    ability: DeviceNetworkBaseAbility | None = None
    transfer_policy: DeviceNetworkTransferPolicy | None = None
    lan_interfaces: list[DeviceLanInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
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

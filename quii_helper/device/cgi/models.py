"""Typed models for read-only device CGI responses.

Check each response's error before interpreting its values: zero is success.
Optional fields are None when absent or unparseable, not proof of a disabled
feature. Empty strings/lists preserve missing data. Native numeric scales,
identifiers and enum values are not normalized unless stated explicitly.
Raw responses are unredacted and may contain private device/account data.
"""

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
    """One storage disk/card entry reported by `get.hdd.base`.

    Attributes:
        exists: Whether the parser recognized the disk as present.
        disk_id: Native disk identifier.
        status: Original device status token.
        name: Device-reported disk name.
        attributes: Native disk attribute string.
        type: Native disk/card type token.
        total: Native total capacity; no conversion to bytes is performed.
        free: Native free capacity, in the same units as total.
        group_id: Native storage-group identifier.
    """

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

    Attributes:
        error: Device result code; zero is success.
        total_sum: Reported aggregate capacity; units are firmware-specific.
        free_sum: Aggregate free capacity in the same units as total_sum.
        disks: Reported disk/card entries.
        mode: Native storage-mode token.
        group_max: Native storage-group limit string.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        exists: Whether the parser recognized the card as present.
        disk_id: Native card/disk identifier, if reported.
        status: Mapped TF_CARD_STATUS_* constant; -1 means unknown.
        status_raw: Original firmware status token.
        total: Native total capacity; no conversion to bytes is performed.
        free: Native free capacity in the same units as total.
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

    Attributes:
        error: Device result code; zero is success.
        formatting: Whether the device reports formatting in progress.
        total_sum: Reported aggregate capacity; units are firmware-specific.
        free_sum: Aggregate free capacity in the same units as total_sum.
        disks: Reported TF-card entries.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        mac: Device MAC address string, if reported.
        version: Installed firmware version, not an available update version.
        release_date: Firmware release-date string as reported.
        model: Device model string; an empty value is not an identification.
        raw: Unredacted parsed response, if available.
    """

    error: int
    mac: str = ""
    version: str = ""
    release_date: str = ""
    model: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceTimeInfo:
    """Device time and timezone reported by `get.product.time`.

    Attributes:
        error: Device result code; zero is success.
        time_zone: Native timezone token, not necessarily an IANA zone name.
        date_time: Device-local clock string; no UTC conversion is performed.
        raw: Unredacted parsed response, if available.
    """

    error: int
    time_zone: str = ""
    date_time: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceStreamKeyInfo:
    """Stream key metadata reported by `get.device.streamkey`.

    Attributes:
        error: Device result code; zero is success.
        key: Sensitive device-reported stream key; never log it.
        tdc: Opaque native key metadata, not an established expiration time.
        sync_time: Original device synchronization-time string.
        raw: Unredacted parsed response, potentially including the key.
    """

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

    Attributes:
        error: Device result code; zero is success.
        qr_code: Original QR payload, potentially containing private device data.
        raw: Unredacted parsed response, if available.
    """

    error: int
    qr_code: str = ""
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceRecordScheduleTime:
    """One `time1`...`time6` record schedule entry.

    `record_type`, `start`, and `end` mirror the original app's
    `QvScheduleTimeInfo(type, start, end)` fields.

    Attributes:
        slot: Slot number from time1 through time6.
        record_type: Native recording-mode token for the slot.
        start: Device-local start-time string.
        end: Device-local end-time string.
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

    Attributes:
        error: Device result code; zero is success.
        channel_id: Native channel identifier, without index conversion.
        record_stream: Configured archive stream token, not live quality.
        prerecord: Native pre-recording setting; units are not converted.
        redundancy: Whether redundant recording is enabled, if reported.
        packet_length: Native recording-segment length; units not converted.
        record_control: Native recording-control mode token.
        schedule: Native weekday tokens mapped to local-time recording slots.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        session_id: Opaque identifier for subsequent archive page requests.
        raw: Unredacted parsed response, if available.
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

    `picture_index` preserves the native `idx` selector (not `record_id`).
    `frame_rate` comes from `idf`; `file_size` preserves the CGI value, which
    the inspected apps interpret as KiB, not an exact JPEG byte length.
    Selectors may be flat or inside `address`; nonblank flat values win.
    Unexposed address fields remain available in `raw`.

    Attributes:
        record_id: Opaque record identifier; not the JPEG idx selector.
        file_name: Remote filename/selector, not a trusted local output path.
        file_type: Native media type, commonly video or picture.
        occur_type: Native trigger such as manual/event; not a confirmed call.
        channel_id: Native archive-channel identifier, without index conversion.
        start_time: Original device-local start timestamp; no UTC conversion.
        end_time: Original end timestamp, possibly empty for a picture.
        stream: Native archive stream selector, not a live-quality override.
        file_size: Native size interpreted as KiB by the inspected clients;
            not an exact downloadable byte count. None means unreported.
        url: Original remote URL, possibly private; not automatically followed.
        raw: Unredacted record fields, including unexposed address metadata.
        picture_index: Native idx used to select an archived JPEG.
        frame_rate: Native idf frame-rate metadata, if reported.
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
    picture_index: str = ""
    frame_rate: int | None = None


@dataclass(frozen=True)
class DeviceRecordMessageInfo:
    """Archive record list page returned by `get.record.message`.

    `result` preserves the native paging/status value when firmware provides
    it. The original client keeps requesting `get.record.message` until that
    value becomes `0`.

    Attributes:
        error: Device result code; zero is success.
        records: Parsed entries in this native page.
        result: Native paging status; zero marks the end, None means absent.
        raw: Unredacted parsed response, if available.
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

    A high-level logical all result has no single session: session_id is empty
    and session is None. Its searches maps attempted video/picture searches to
    their individual results; pages is their native, unfiltered concatenation.
    A failed/incomplete combined result exposes no partial aggregate records.

    Attributes:
        error: Device result code, or the first failed subquery's code.
        session_id: Native session id for one type; empty for combined all.
        records: Collected entries; the high-level API filters them to the
            requested inclusive interval. Combined all exposes these only
            after both searches complete.
        pages: Native unfiltered pages, potentially outside the requested times.
        completed: Whether every required native search finished within limits.
        session: Single native search response; None for combined all.
        searches: Attempted video/picture subqueries for combined all, each
            retaining its own session, status and pages; empty for one type.
    """

    error: int
    session_id: str = ""
    records: list[DeviceRecordFileInfo] = field(default_factory=list)
    pages: list[DeviceRecordMessageInfo] = field(default_factory=list)
    completed: bool = False
    session: DeviceRecordSessionInfo | None = None
    searches: "dict[str, DeviceRecordListInfo]" = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceRecordAlarmInfo:
    """Alarm-linked archive records returned by `get.record.alarmrecord`.

    The original app sends one timestamp plus optional alarm identifiers, then
    parses the response with the same record-list parser used for archive pages.

    Attributes:
        error: Device result code; zero is success.
        records: Archive entries associated with the requested alarm selector.
        result: Native result/paging status; None if not reported.
        raw: Unredacted parsed response, if available.
    """

    error: int
    records: list[DeviceRecordFileInfo] = field(default_factory=list)
    result: int | None = None
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmChannel:
    """One alarm channel returned by `get.encode.channelname`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        name: Device-reported channel name.
        channel_type: Native channel-type token.
        serial_no: Device-reported channel serial/index value.
    """

    channel_id: int | None = None
    name: str = ""
    channel_type: str = ""
    serial_no: int | None = None


@dataclass(frozen=True)
class DeviceAlarmChannelInfo:
    """Alarm channel list returned by `get.encode.channelname`.

    Attributes:
        error: Device result code; zero is success.
        channels: Reported channel entries, not inferred from a fixed count.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channels: list[DeviceAlarmChannel] = field(default_factory=list)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceWifiNetwork:
    """One Wi-Fi network entry reported by `get.wifi.list`.

    Attributes:
        network_id: Native scan-result identifier.
        ssid: Wireless network name, potentially private.
        rssi: Native signal-strength value; no scale conversion is performed.
        is_encrypted: Parser interpretation of the native encryption flag.
    """

    network_id: str = ""
    ssid: str = ""
    rssi: int | None = None
    is_encrypted: bool | None = None


@dataclass(frozen=True)
class DeviceWifiListInfo:
    """Available Wi-Fi networks reported by `get.wifi.list`.

    Attributes:
        error: Device result code; zero is success.
        networks: Parsed Wi-Fi entries with nonempty SSIDs.
        raw: Unredacted parsed response, if available.
    """

    error: int
    networks: list[DeviceWifiNetwork] = field(default_factory=list)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceScreenFlipInfo:
    """Screen flip state reported by `get.shape.mirror`.

    `state` and `angle` follow the original app's `QvDeviceScreenFlipState`
    mapping. Raw string values are preserved for firmware-specific callers.

    Attributes:
        error: Device result code; zero is success.
        mirror: Original mirror token.
        rotate: Original rotation token.
        state: One for up_down mirroring, zero otherwise, including unknown.
        angle: Parser-mapped rotation angle in degrees; zero if unrecognized.
        raw: Unredacted parsed response, if available.
    """

    error: int
    mirror: str = ""
    rotate: str = ""
    state: int = 0
    angle: int = 0
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceVideoSwitchInfo:
    """Video on/off state reported by `get.videoswitch.vionoff`.

    Attributes:
        error: Device result code; zero is success.
        value: Original video-switch token.
        state: One for video_on, zero otherwise, including missing values.
        is_on: Whether the token is exactly video_on; check error first.
        raw: Unredacted parsed response, if available.
    """

    error: int
    value: str = ""
    state: int = 0
    is_on: bool = False
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceTimeTitleOverlay:
    """One time-title overlay geometry entry from `get.video.timetitle`.

    Attributes:
        stream_type: Native stream selector for this overlay.
        video_width: Reported video width.
        video_height: Reported video height.
        title_width: Reported overlay width in the native coordinate system.
        title_height: Reported overlay height in the native coordinate system.
        location_x: Native horizontal overlay coordinate.
        location_y: Native vertical overlay coordinate.
    """

    stream_type: int | None = None
    video_width: int | None = None
    video_height: int | None = None
    title_width: int | None = None
    title_height: int | None = None
    location_x: int | None = None
    location_y: int | None = None


@dataclass(frozen=True)
class DeviceTimeTitleInfo:
    """Time-title overlay geometry reported by `get.video.timetitle`.

    Attributes:
        error: Device result code; zero is success.
        overlays: Reported stream-specific overlay geometry entries.
        raw: Unredacted parsed response, if available.
    """

    error: int
    overlays: list[DeviceTimeTitleOverlay] = field(default_factory=list)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAttachmentProfile:
    """Sub-device profile reported by `get.device.attachInfo`.

    The original app maps `channelinfo` into `QvDeviceAttachmentInfo.Profile`.

    Attributes:
        total_channel_num: Total attached-channel count reported by the device.
        cam_num: Reported camera/panel count.
        cctv_num: Reported CCTV channel count.
        ipg_num: Reported native ipg channel count; category is firmware-specific.
        manage_num: Reported management channel count.
        ep_num: Native ep channel count; meaning depends on firmware.
        switch_direct: Native direct-switch capability flag.
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
    """One channel lock entry reported by `get.device.attachInfo`.

    Attributes:
        lock_id: Native attached-lock identifier.
        name: Device-reported lock name.
        enabled: Whether the lock is advertised as enabled, if reported.
    """

    lock_id: int | None = None
    name: str = ""
    enabled: bool | None = None


@dataclass(frozen=True)
class DeviceAttachmentChannel:
    """One attached channel reported by `get.device.attachInfo`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        name: Device-reported panel/channel name.
        channel_type: Native channel-type token.
        sub_type: Native subtype code; zero is the parser default.
        enabled: Whether this channel is advertised as enabled.
        video_enabled: Whether this channel advertises video support.
        talk_enabled: Whether this channel advertises talk support.
        cctv_type: Native CCTV-type code, if reported.
        locks: Reported locks attached to this channel.
    """

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
    """One elevator attachment reported by `get.device.attachInfo`.

    Attributes:
        elevator_id: Native attached-elevator identifier.
        enabled: Whether the elevator attachment is enabled, if reported.
    """

    elevator_id: int | None = None
    enabled: bool | None = None


@dataclass(frozen=True)
class DeviceAttachmentAlarm:
    """Alarm attachment state reported by `get.device.attachInfo`.

    Attributes:
        enabled: Whether the alarm attachment is enabled, if reported.
        mode: Native alarm-mode code.
        numbers: Reported alarm attachment count.
        arming_type: Native arming code; three is the parser default.
    """

    enabled: bool | None = None
    mode: int | None = None
    numbers: int | None = None
    arming_type: int = 3


@dataclass(frozen=True)
class DeviceAttachmentSmartSwitch:
    """Smart switch attachment state reported by `get.device.attachInfo`.

    Attributes:
        enabled: Whether smart-switch attachment is enabled, if reported.
        room: Native room value reported by the attachment profile.
        total: Reported smart-switch total.
    """

    enabled: bool | None = None
    room: int | None = None
    total: int | None = None


@dataclass(frozen=True)
class DeviceAttachmentInfo:
    """Sub-device attachment information from `get.device.attachInfo`.

    This mirrors the original app's XML `GetDeviceAttachmentResp` mapping into
    `QvDeviceAttachmentInfo` and keeps raw parsed content for vendor-specific
    fields.

    Attributes:
        error: Device result code; zero is success.
        profile: Aggregate attached-channel counts and capabilities, if present.
        channels: Reported attached panels/channels and their locks.
        elevators: Reported elevator attachments.
        alarms: Reported alarm attachments.
        smart_switches: Reported smart-switch attachments.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        channel_id: Native channel identifier, without index conversion.
        enabled: Whether motion detection is enabled, if reported.
        sensitivity: Device-scaled sensitivity, not a universal percentage.
        range: Original detection-range string.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        channel_id: Native channel identifier, without index conversion.
        enabled: Whether the motion alarm is enabled, if reported.
        sensitivity: Device-scaled detection sensitivity.
        peds_enabled: Native pedestrian-detection flag, not a normalized bool.
        row_num: Reported number of detection-grid rows.
        col_num: Reported number of detection-grid columns.
        region_data: Encoded detection-region rows.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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
    """Video-lost alarm state reported by `get.alarm.videolost`.

    Attributes:
        error: Device result code; zero is success.
        channel_id: Native channel identifier, without index conversion.
        enabled: Whether video-loss detection is enabled, if reported.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmVideoShelterInfo:
    """Video-shelter alarm state reported by `get.alarm.videoshelter`.

    Attributes:
        error: Device result code; zero is success.
        channel_id: Native channel identifier, without index conversion.
        enabled: Whether camera-obstruction detection is enabled, if reported.
        sensitivity: Device-scaled obstruction-detection sensitivity.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channel_id: int | None = None
    enabled: bool | None = None
    sensitivity: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmInputChannel:
    """One alarm input channel returned by `get.alarm.alarmin`.

    Attributes:
        channel_id: Native input-channel identifier, without index conversion.
        enabled: Whether the input is enabled, if reported.
        input_type: Native electrical/input-mode token.
        name: Device-reported input name.
    """

    channel_id: int | None = None
    enabled: bool | None = None
    input_type: str = ""
    name: str = ""


@dataclass(frozen=True)
class DeviceAlarmInputInfo:
    """Alarm input channel list returned by `get.alarm.alarmin`.

    Attributes:
        error: Device result code; zero is success.
        channels: Reported input configurations, not live input events.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channels: list[DeviceAlarmInputChannel] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmScheduleSlot:
    """One alarm schedule time slot from `get.alarm.*.schedule`.

    Attributes:
        slot: Slot number parsed from the native timeN entry.
        enabled: Whether this schedule slot is enabled, if reported.
        start: Device-local start-time string.
        end: Device-local end-time string.
    """

    slot: int
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DeviceAlarmScheduleDay:
    """One weekday schedule from `get.alarm.*.schedule`.

    Attributes:
        day: Original device weekday token.
        slots: Schedule slots reported for this weekday.
    """

    day: str
    slots: list[DeviceAlarmScheduleSlot] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmScheduleInfo:
    """Alarm schedule returned by one `get.alarm.*.schedule` command.

    Attributes:
        error: Device result code; zero is success.
        alarm_type: Native alarm family selected by the query.
        channel_id: Native channel identifier, without index conversion.
        days: Weekday tokens mapped to device-local schedules.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    alarm_type: str = ""
    channel_id: int | None = None
    days: dict[str, DeviceAlarmScheduleDay] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceHumanTraceInfo:
    """Human-trace state reported by `get.humantrace.info`.

    Attributes:
        error: Device result code; zero is success.
        enabled: Whether human tracking is enabled, if reported.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceMoveDetectionInfo:
    """Move-detection state reported by `get.movedetection.info`.

    Attributes:
        error: Device result code; zero is success.
        enabled: Whether movement detection is enabled, if reported.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    enabled: bool | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DevicePtzStateInfo:
    """Pan/tilt position reported by `get.ptz.position`.

    The original app maps this response into `QvDevicePanTiltControlState`.

    Attributes:
        error: Device result code; zero is success.
        position_x: Native horizontal position; not converted to degrees.
        position_y: Native vertical position; not converted to degrees.
        min_x: Reported minimum horizontal position in native units.
        max_x: Reported maximum horizontal position in native units.
        min_y: Reported minimum vertical position in native units.
        max_y: Reported maximum vertical position in native units.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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
    """One PTZ preset reported by `get.ptz.preset`.

    Attributes:
        preset_id: Native preset identifier, not a list position.
        name: Device-reported preset name.
    """

    preset_id: str = ""
    name: str = ""


@dataclass(frozen=True)
class DevicePtzPresetInfo:
    """PTZ preset list reported by `get.ptz.preset`.

    Attributes:
        error: Device result code; zero is success.
        presets: Reported preset entries; this read moves no camera.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    presets: list[DevicePtzPreset] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceUpgradeVersionInfo:
    """Latest firmware version reported by `get.system.upgradeversion`.

    The original app maps this response into `QvDeviceLatestVersionInfo`.

    Attributes:
        error: Device result code; zero is success.
        version: Latest firmware version advertised by the device.
        release_time: Original release-time string, not converted to UTC.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available; no update is installed.
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

    Attributes:
        error: Device result code; zero is success.
        status: Native upgrade-state code; None means not reported.
        version: Version associated with the reported upgrade state.
        time: Original device upgrade-time string.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available; no update is started.
    """

    error: int
    status: int | None = None
    version: str = ""
    time: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceUpgradeProcessInfo:
    """Firmware upgrade progress reported by `get.system.upgradeprocess`.

    Attributes:
        error: Device result code; zero is success.
        process: Native progress value; no scale conversion is performed.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available; no update is started.
    """

    error: int
    process: int | None = None
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFpsChannelInfo:
    """One channel/stream FPS entry reported by `get.encode.fps`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        stream_id: Native stream identifier, not a high/low alias.
        fps: Device-reported frames per second, not measured receive FPS.
    """

    channel_id: int
    stream_id: int
    fps: int


@dataclass(frozen=True)
class DeviceFpsInfo:
    """FPS values reported by `get.encode.fps`.

    The original app maps this command into `QvDeviceFpsInfo`.

    Attributes:
        error: Device result code; zero is success.
        channels: Reported channel/stream frame-rate settings.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channels: list[DeviceFpsChannelInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSmartLightItem:
    """One smart-light entry reported by `get.smart.lightinfo`.

    Attributes:
        light_no: Native light identifier.
        name: Device-reported light name.
        state: Native light-state code, not a normalized boolean.
    """

    light_no: int | None = None
    name: str = ""
    state: int | None = None


@dataclass(frozen=True)
class DeviceSmartLightInfo:
    """Smart-light room state reported by `get.smart.lightinfo`.

    The original app maps this command into `QvDeviceSmartLightInfo`.

    Attributes:
        error: Device result code; zero is success.
        room: Native room identifier.
        light_num: Reported light count, not list completeness.
        lights: Parsed smart-light entries.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    room: int | None = None
    light_num: int | None = None
    lights: list[DeviceSmartLightItem] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSoundLightChannelInfo:
    """One channel entry reported by `get.soundandlight.state`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        ctrl_state: Native sound/light control-state code.
    """

    channel_id: str = ""
    ctrl_state: int | None = None


@dataclass(frozen=True)
class DeviceSoundLightInfo:
    """Sound-and-light one-key control state.

    The original app maps this command into `QvDeviceSoundLightControlInfo`.

    Attributes:
        error: Device result code; zero is success.
        channels: Reported per-channel control states.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
    """

    error: int
    channels: list[DeviceSoundLightChannelInfo] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    raw: DeviceCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLanInfo:
    """One LAN interface reported inside `get.network.config`.

    Attributes:
        name: Device-reported interface name.
        ip_address: Reported interface IP address, not a reachability check.
        subnet_mask: Reported IP subnet mask.
        gateway: Reported default gateway address.
        mac: Reported interface MAC address.
        dhcp: Whether DHCP is enabled, if reported.
        network_type: Selected native network-type token.
        supported_network_types: Original supported-network-types string.
    """

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

    Attributes:
        error: Device result code; zero is success.
        address: Reported primary IP address, not a reachability check.
        subnet_mask: Reported primary subnet mask.
        gateway: Reported default gateway address.
        dhcp: Whether DHCP is enabled, if reported.
        lan_interfaces: Reported individual interface configurations.
        raw: Unredacted parsed response, if available.
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
    """Network-base capability flags reported by `get.network.base`.

    Attributes:
        valid: Native validity flag; None means not reported.
        support_dhcp: Native DHCP-support flag.
        support_inner_ip: Native internal-IP support flag.
        support_multi_eth: Native multiple-interface support flag.
    """

    valid: int | None = None
    support_dhcp: int | None = None
    support_inner_ip: int | None = None
    support_multi_eth: int | None = None


@dataclass(frozen=True)
class DeviceNetworkTransferPolicy:
    """Transfer policy value reported by `get.network.base`.

    Attributes:
        value: Currently selected native transfer-policy token.
        supported: Original supported-policy string, not split or normalized.
    """

    value: str = ""
    supported: str = ""


@dataclass(frozen=True)
class DeviceNetworkBaseInfo:
    """Extended network base settings reported by `get.network.base`.

    The original app requests this command for VSU devices and maps the
    response from `GetNetworkBaseResp`.

    Attributes:
        error: Device result code; zero is success.
        dns: Reported primary DNS server address.
        secondary_dns: Reported secondary DNS server address.
        http_port: Configured native HTTP port, if reported.
        media_port: Configured native media port, if reported.
        rtsp_port: Configured device RTSP port, not this library's RTSP port.
        rtsp_url: Original device RTSP URL, potentially containing secrets.
        handset_port: Native handset-service port, if reported.
        max_users: Device-reported user/client limit.
        transfer_mode: Normalized native transfer-mode flag, if reported.
        hs_download: Whether high-speed download is advertised, if reported.
        ability: Native network capability flags, if present.
        transfer_policy: Current and supported transfer-policy tokens.
        lan_interfaces: Reported individual interface configurations.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        language: Native language token.
        auto_sync_time: Whether automatic time synchronization is enabled.
        time_zone: Native timezone token, not necessarily an IANA zone name.
        date_time: Original device-local clock string; no UTC conversion.
        device_id: Device-reported identifier, potentially private.
        host_name: Configured device hostname.
        date_split: Native displayed-date separator.
        date_format: Native displayed-date format token.
        time_format: Native displayed-time format token.
        on_storage_full: Native full-storage behavior token.
        video_standard: Configured video standard token, such as PAL/NTSC.
        auto_logout: Native automatic-logout setting; no unit conversion.
        startup_wizard: Whether the startup wizard is enabled, if reported.
        smart_display: Native smart-display flag, if reported.
        smart_tracking: Native smart-tracking flag, if reported.
        preview_strategy: Native preview-policy token.
        support_host_name: Whether hostname configuration is advertised.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        wifi: Native Wi-Fi capability value; None means not reported.
        rtsp: Native device RTSP capability, not library RTSP support.
        snap: Native snapshot capability value.
        talk: Native talk capability; not proof of audible playback.
        ptz: Native pan/tilt/zoom capability value.
        ptz_preset: Native PTZ-preset capability value.
        https: Native HTTPS capability value.
        ntp: Native time-synchronization capability value.
        cloud: Native cloud capability value.
        cloud_storage: Native cloud-storage capability value.
        cloud_upgrade: Native cloud-upgrade capability value.
        automatic_ip: Native automatic-IP capability value.
        motion_detection: Native motion-detection capability value.
        alarm_in: Native alarm-input capability value.
        video_lost: Native video-loss detection capability value.
        video_shelter: Native camera-obstruction detection capability value.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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
    """One encode stream entry reported by `get.encode`.

    Attributes:
        name: Native stream block name, such as mainstream or substream.
        enabled: Whether this stream is enabled, if reported.
        compression: Configured native codec/compression token.
        resolution: Configured resolution token, not measured frame dimensions.
        bitrate: Native configured bitrate; units are not converted.
        bitrate_control: Native rate-control token, such as CBR/VBR.
        fps: Configured frames per second, not measured receive FPS.
        gop: Native GOP/keyframe-interval setting.
        quality: Native encoder-quality value, not the live high/low selector.
        audio_enabled: Whether audio encoding is enabled, if reported.
        h264plus_enabled: Native H.264+ encoding flag, if reported.
        raw: Unredacted stream block, retaining vendor-specific fields.
    """

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
    """One video channel reported by `get.encode`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        name: Device-reported channel name.
        ability: Original channel capability string.
        encode_new: Native newer-encoding flag, if reported.
        video_mode: Native video-mode token.
        protocol: Native channel-protocol token.
        streams: Parsed stream blocks advertised by this channel.
        raw: Unredacted channel block, retaining vendor-specific fields.
    """

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

    Attributes:
        error: Device result code; zero is success.
        channels: Reported channels and their configured encoding streams.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

    Attributes:
        error: Device result code; zero is success.
        model: Reported device model string.
        version: Installed firmware version string.
        release_date: Installed firmware release-date string.
        latest_version: Latest firmware version advertised by the device.
        latest_release_date: Advertised update release-date string.
        mac: Reported device MAC address.
        ssid: Reported wireless network name, potentially private.
        rssi: Native wireless signal-strength value; no scale conversion.
        time_zone: Native timezone token, not necessarily an IANA zone name.
        total_sum: Native total storage capacity; units are firmware-specific.
        free_sum: Native free capacity in the same units as total_sum.
        content: Unredacted parsed content, retaining vendor-specific fields.
        raw: Unredacted parsed response, if available.
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

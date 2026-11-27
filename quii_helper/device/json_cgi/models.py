"""Typed models for read-only JSON `/tdkcgi` responses.

Check each response's error before interpreting its values: zero is success.
Optional fields are None when absent or unparseable, not proof of a disabled
feature. Empty strings/lists preserve missing data. Native numeric scales,
identifiers and enum values are not normalized unless stated explicitly.
Raw responses are unredacted and may contain private device/account data.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceJsonCgiResponse:
    """Raw parsed JSON `/tdkcgi` response.

    Attributes:
        command: Requested JSON CGI command.
        error: Numeric device error code from `body.error`.
        content: Parsed `body.content` JSON object.
        raw: Original decoded JSON response.
    """

    command: str
    error: int
    content: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class DeviceAudioVolumeRange:
    """One audio volume range reported by `get.audio.outvolume`.

    Attributes:
        level: Current device-scaled volume; not necessarily a percentage.
        min_level: Reported minimum allowed volume.
        max_level: Reported maximum allowed volume.
    """

    level: int | None = None
    min_level: int | None = None
    max_level: int | None = None


@dataclass(frozen=True)
class DeviceAudioVolumeInfo:
    """Audio output volume reported by `get.audio.outvolume`.

    Attributes:
        error: Device result code; zero is success.
        prompt: Prompt/ringtone volume settings, or None if not reported.
        talk: Conversation output volume settings, or None if not reported.
        raw: Unredacted parsed response, if available.
    """

    error: int
    prompt: DeviceAudioVolumeRange | None = None
    talk: DeviceAudioVolumeRange | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAudioSessionInfo:
    """Audio file session reported by JSON `get.audio.session`.

    Attributes:
        error: Device result code; zero is success.
        session: Opaque audio-file session identifier, not a live talk handle.
        file_id: Device audio-file identifier associated with the session.
        raw: Unredacted parsed response, if available.
    """

    error: int
    session: str = ""
    file_id: str = ""
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmIntervalInfo:
    """Alarm interval reported by JSON `get.alarm.detailInfo`.

    Attributes:
        value: Selected native alarm interval; units are firmware-specific.
        range: Reported allowed interval values, without unit conversion.
    """

    value: int | None = None
    range: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmLevelInfo:
    """One alarm sensitivity level entry from JSON `get.alarm.detailInfo`.

    Attributes:
        level_id: Native sensitivity-level identifier.
        value: Associated device-scaled sensitivity value.
    """

    level_id: int | None = None
    value: int | None = None


@dataclass(frozen=True)
class DeviceAlarmRegionInfo:
    """Alarm detection region reported by JSON `get.alarm.detailInfo`.

    Attributes:
        row_num: Reported number of region-grid rows.
        col_num: Reported number of region-grid columns.
        data: Encoded region rows, preserved without geometry conversion.
    """

    row_num: int | None = None
    col_num: int | None = None
    data: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmSmartFilterInfo:
    """Smart-filter flags reported by JSON `get.alarm.detailInfo`.

    Attributes:
        peds: Native pedestrian-filter flag; None means not reported.
        vehc: Native vehicle-filter flag; None means not reported.
    """

    peds: int | None = None
    vehc: int | None = None


@dataclass(frozen=True)
class DeviceAlarmChannelDetailInfo:
    """Per-channel alarm configuration from JSON `get.alarm.detailInfo`.

    Attributes:
        channel_id: Native channel identifier, without index conversion.
        enabled: Whether this alarm is enabled, if reported.
        sensitivity: Selected device-scaled sensitivity.
        max_sensitivity: Maximum sensitivity reported by the device.
        move_enabled: Motion-linkage flag, if reported.
        record_enabled: Whether alarm recording linkage is enabled.
        alarm_light_enabled: Whether alarm-light linkage is enabled.
        whistle_enabled: Whether audible alarm linkage is enabled.
        only_track: Tracking-only flag, if reported.
        record_latch: Native recording latch duration; units are not converted.
        schedule_mode: Native schedule mode string.
        interval: Alarm interval and supported values, if reported.
        levels: Reported sensitivity-level entries.
        region: Detection grid, if reported.
        smart_filter: Pedestrian/vehicle filter flags, if reported.
        schedule: Device-local weekday schedules.
    """

    channel_id: int | None = None
    enabled: bool | None = None
    sensitivity: int | None = None
    max_sensitivity: int | None = None
    move_enabled: bool | None = None
    record_enabled: bool | None = None
    alarm_light_enabled: bool | None = None
    whistle_enabled: bool | None = None
    only_track: bool | None = None
    record_latch: int | None = None
    schedule_mode: str = ""
    interval: DeviceAlarmIntervalInfo | None = None
    levels: list[DeviceAlarmLevelInfo] = field(default_factory=list)
    region: DeviceAlarmRegionInfo | None = None
    smart_filter: DeviceAlarmSmartFilterInfo | None = None
    schedule: "list[DevicePirScheduleDayInfo]" = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmDetailInfo:
    """Alarm detail configuration reported by JSON `get.alarm.detailInfo`.

    Attributes:
        error: Device result code; zero is success.
        alarm_type: Native alarm-type selector, if reported.
        channel: Parsed channel configuration, or None if absent.
        raw: Unredacted parsed response, if available.
    """

    error: int
    alarm_type: int | None = None
    channel: DeviceAlarmChannelDetailInfo | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmStatusInfo:
    """Alarm status reported by custom JSON `get.alarm.status`.

    Attributes:
        error: Device result code; zero is success.
        status: Original device status string.
        is_on: Normalized on/off state; None for unknown or missing values.
        raw: Unredacted parsed response, if available.
    """

    error: int
    status: str = ""
    is_on: bool | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceHardwareInfo:
    """Battery and charge state reported by JSON `getHWInfo`.

    Attributes:
        error: Device result code; zero is success.
        battery_quantity: Reported battery quantity; scale is firmware-specific.
        voltmeter_temperature: Native voltameterTemp divided by ten; the
            parser does not establish a physical unit.
        charge_source: Native power/charging-source code.
        charge_status: Native charging-state code.
        raw: Unredacted parsed response, if available.
    """

    error: int
    battery_quantity: int | None = None
    voltmeter_temperature: float | None = None
    charge_source: int | None = None
    charge_status: int | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLightItemInfo:
    """One room light reported by JSON `get.light.info`.

    Attributes:
        number: Native light identifier.
        name: Device-reported display name.
        status: Native light-state code, not a normalized boolean.
        brightness: Device-scaled brightness, not necessarily a percentage.
    """

    number: int | None = None
    name: str = ""
    status: int | None = None
    brightness: int | None = None


@dataclass(frozen=True)
class DeviceLightRoomInfo:
    """One light room reported by JSON `get.light.info`.

    Attributes:
        number: Native room identifier.
        name: Device-reported room name.
        lights: Lights reported inside this room.
    """

    number: int | None = None
    name: str = ""
    lights: list[DeviceLightItemInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceLightInfo:
    """Room light state reported by JSON `get.light.info`.

    Attributes:
        error: Device result code; zero is success.
        rooms: Reported rooms and their light entries.
        raw: Unredacted parsed response, if available.
    """

    error: int
    rooms: list[DeviceLightRoomInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DevicePirScheduleSlotInfo:
    """One PIR schedule slot reported by JSON `getPIRCfg`.

    Attributes:
        section: Native schedule-section identifier.
        enabled: Whether the slot is enabled, if reported.
        start: Device-local start time string; no timezone conversion.
        end: Device-local end time string; no timezone conversion.
    """

    section: str = ""
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DevicePirScheduleDayInfo:
    """One PIR schedule day reported by JSON `getPIRCfg`.

    Attributes:
        week: Original device weekday token.
        week_index: Monday=0 through Sunday=6; None for an unknown weekday.
        slots: Time slots reported for this weekday.
    """

    week: str = ""
    week_index: int | None = None
    slots: list[DevicePirScheduleSlotInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DevicePirConfigInfo:
    """PIR sensor configuration reported by JSON `getPIRCfg`.

    Attributes:
        error: Device result code; zero is success.
        enabled: Whether PIR detection is enabled, if reported.
        sensitivity: Device-scaled PIR sensitivity.
        link_record: Whether detection links to recording, if reported.
        schedule: Device-local detection schedules.
        raw: Unredacted parsed response, if available.
    """

    error: int
    enabled: bool | None = None
    sensitivity: int | None = None
    link_record: bool | None = None
    schedule: list[DevicePirScheduleDayInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceThirdPartyPushScheduleSlotInfo:
    """One third-party push schedule slot from `get.thirdpartypush.info`.

    Attributes:
        section: Native schedule-section identifier.
        enabled: Whether the slot is enabled, if reported.
        start: Device-local start time string; no timezone conversion.
        end: Device-local end time string; no timezone conversion.
    """

    section: str = ""
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DeviceThirdPartyPushScheduleDayInfo:
    """One third-party push schedule day from `get.thirdpartypush.info`.

    Attributes:
        week: Original device weekday token.
        week_index: Monday=0 through Sunday=6; None for an unknown weekday.
        slots: Time slots reported for this weekday.
    """

    week: str = ""
    week_index: int | None = None
    slots: list[DeviceThirdPartyPushScheduleSlotInfo] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class DeviceThirdPartyPushInfo:
    """Third-party alarm push settings from JSON `get.thirdpartypush.info`.

    Attributes:
        error: Device result code; zero is success.
        account: Configured third-party account; may be private.
        area_code: Configured account/phone region code.
        push_enabled: Whether third-party push is enabled, if reported.
        third_party_type: Native third-party provider/type code.
        upload_type: Native upload-mode code.
        event_types: Configured native event-type codes.
        supported_event_types: Event-type codes advertised as supported.
        schedule: Device-local notification schedules.
        raw: Unredacted parsed response, if available; not a push registration.
    """

    error: int
    account: str = ""
    area_code: str = ""
    push_enabled: bool | None = None
    third_party_type: int | None = None
    upload_type: int | None = None
    event_types: list[int] = field(default_factory=list)
    supported_event_types: list[int] = field(default_factory=list)
    schedule: list[DeviceThirdPartyPushScheduleDayInfo] = field(
        default_factory=list
    )
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceJsonFpsModeInfo:
    """FPS mode reported by JSON `get.fps.mode`.

    Attributes:
        error: Device result code; zero is success.
        mode: Native mode code, not a measured video frame rate.
        raw: Unredacted parsed response, if available.
    """

    error: int
    mode: int | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceBabysitterStateInfo:
    """Babysitter mode state reported by `get.babysitter`.

    Attributes:
        error: Device result code; zero is success.
        mode: Whether the device reports babysitter mode enabled.
        raw: Unredacted parsed response, if available.
    """

    error: int
    mode: bool | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLockTimeInfo:
    """Unlock time range reported for one lock by `get.lock.status`.

    Attributes:
        min: Minimum native unlock duration; units are firmware-specific.
        max: Maximum native unlock duration in the same units as min.
        current: Configured duration in the same native units; no command sent.
    """

    min: float | None = None
    max: float | None = None
    current: float | None = None


@dataclass(frozen=True)
class DeviceLockInfo:
    """One lock entry reported by JSON `get.lock.status`.

    Attributes:
        lock_id: Native lock identifier.
        name: Device-reported lock name.
        time: Configured unlock-duration range, if reported.
    """

    lock_id: int | None = None
    name: str = ""
    time: DeviceLockTimeInfo | None = None


@dataclass(frozen=True)
class DeviceLockStatusInfo:
    """Lock configuration/status reported by `get.lock.status`.

    Attributes:
        error: Device result code; zero is success.
        locks: Reported lock configurations; not proof of physical door state.
        raw: Unredacted parsed response, if available.
    """

    error: int
    locks: list[DeviceLockInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceCityCoordinateInfo:
    """City coordinates and sun times from JSON `get.city.coordinate`.

    Attributes:
        error: Device result code; zero is success.
        latitude: Latitude as reported, without coordinate conversion.
        longitude: Longitude as reported, without coordinate conversion.
        sunrise: Device-reported local sunrise string.
        sunset: Device-reported local sunset string.
        raw: Unredacted parsed response, if available.
    """

    error: int
    latitude: float | None = None
    longitude: float | None = None
    sunrise: str = ""
    sunset: str = ""
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFloodlightInfo:
    """One floodlight entry reported by JSON `get.floodlight.switch`.

    Attributes:
        code: Native floodlight identifier.
        status: Original device status token.
        status_code: Parser-mapped status code, or None if unrecognized.
        brightness: Device-scaled brightness; not necessarily a percentage.
        duration: Native activation duration; units are firmware-specific.
    """

    code: str = ""
    status: str = ""
    status_code: int | None = None
    brightness: int | None = None
    duration: int | None = None


@dataclass(frozen=True)
class DeviceFloodlightSwitchInfo:
    """Floodlight switch state reported by `get.floodlight.switch`.

    Attributes:
        error: Device result code; zero is success.
        lights: Reported floodlight settings and states.
        raw: Unredacted parsed response, if available.
    """

    error: int
    lights: list[DeviceFloodlightInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFloodlightScheduleTimeInfo:
    """One floodlight schedule time entry from `get.floodlight.schedule`.

    Attributes:
        mode: Native fixed-time/sunrise/sunset mode token.
        mode_code: Parser-mapped mode code, or None if unrecognized.
        shift: Native offset from the selected sun time; units not converted.
        time: Device-local fixed-time string when applicable.
    """

    mode: str = ""
    mode_code: int | None = None
    shift: int | None = None
    time: str = ""


@dataclass(frozen=True)
class DeviceFloodlightSchedulePlanInfo:
    """One floodlight schedule plan from `get.floodlight.schedule`.

    Attributes:
        number: Native plan identifier.
        enabled: Whether this plan is enabled, if reported.
        start: Start-time configuration; disabled plans use a cleared value.
        end: End-time configuration; disabled plans use a cleared value.
    """

    number: int | None = None
    enabled: bool | None = None
    start: DeviceFloodlightScheduleTimeInfo | None = None
    end: DeviceFloodlightScheduleTimeInfo | None = None


@dataclass(frozen=True)
class DeviceFloodlightScheduleDayInfo:
    """One floodlight schedule day from `get.floodlight.schedule`.

    Attributes:
        week: Native weekday code, without index conversion.
        plans: Plans reported for this weekday.
    """

    week: int | None = None
    plans: list[DeviceFloodlightSchedulePlanInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceFloodlightScheduleInfo:
    """Floodlight schedule reported by JSON `get.floodlight.schedule`.

    Attributes:
        error: Device result code; zero is success.
        sunrise: Device-reported local sunrise string.
        sunset: Device-reported local sunset string.
        days: Reported weekday schedules.
        raw: Unredacted parsed response, if available.
    """

    error: int
    sunrise: str = ""
    sunset: str = ""
    days: list[DeviceFloodlightScheduleDayInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceVoiceFileInfo:
    """One voice prompt file reported by `get.voice.message`.

    Attributes:
        file_id: Native voice-file identifier, not a filesystem path.
        name: Device-reported voice-file display name.
    """

    file_id: int | None = None
    name: str = ""


@dataclass(frozen=True)
class DeviceVoiceMessageInfo:
    """Voice-message settings reported by `get.voice.message`.

    Attributes:
        error: Device result code; zero is success.
        current_file_id: Currently selected native voice-file identifier.
        mode: Original device mode token.
        mode_code: Parser-mapped voice mode code, or None if unrecognized.
        files: Available voice-file entries reported by the device.
        raw: Unredacted parsed response, if available.
    """

    error: int
    current_file_id: int | None = None
    mode: str = ""
    mode_code: int | None = None
    files: list[DeviceVoiceFileInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSmartSwitchChannelInfo:
    """One smart-switch channel reported by JSON `get.smartswitch.info`.

    Attributes:
        number: Native switch-channel identifier.
        name: Device-reported channel name.
        state: Normalized channel on/off state, if reported.
    """

    number: int | None = None
    name: str = ""
    state: bool | None = None


@dataclass(frozen=True)
class DeviceSmartSwitchItemInfo:
    """One smart switch reported by JSON `get.smartswitch.info`.

    Attributes:
        number: Native switch identifier.
        name: Device-reported switch name.
        online: Whether the device reports the switch online.
        switch_channel_total: Reported channel count, not list completeness.
        channels: Reported switch-channel entries.
    """

    number: int | None = None
    name: str = ""
    online: bool | None = None
    switch_channel_total: int | None = None
    channels: list[DeviceSmartSwitchChannelInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceSmartSwitchRoomInfo:
    """One smart-switch room reported by JSON `get.smartswitch.info`.

    Attributes:
        number: Native room identifier.
        name: Device-reported room name.
        switches: Switches reported inside this room.
    """

    number: int | None = None
    name: str = ""
    switches: list[DeviceSmartSwitchItemInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceSmartSwitchInfo:
    """Smart-switch topology reported by JSON `get.smartswitch.info`.

    Attributes:
        error: Device result code; zero is success.
        add_status: Native add/pairing state code; this read starts no pairing.
        rooms: Reported rooms and their switch entries.
        raw: Unredacted parsed response, if available.
    """

    error: int
    add_status: int | None = None
    rooms: list[DeviceSmartSwitchRoomInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None

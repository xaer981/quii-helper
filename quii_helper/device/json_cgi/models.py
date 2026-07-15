"""Typed models for read-only JSON `/tdkcgi` responses."""

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
    """One audio volume range reported by `get.audio.outvolume`."""

    level: int | None = None
    min_level: int | None = None
    max_level: int | None = None


@dataclass(frozen=True)
class DeviceAudioVolumeInfo:
    """Audio output volume reported by `get.audio.outvolume`."""

    error: int
    prompt: DeviceAudioVolumeRange | None = None
    talk: DeviceAudioVolumeRange | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAudioSessionInfo:
    """Audio file session reported by JSON `get.audio.session`."""

    error: int
    session: str = ""
    file_id: str = ""
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmIntervalInfo:
    """Alarm interval reported by JSON `get.alarm.detailInfo`."""

    value: int | None = None
    range: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmLevelInfo:
    """One alarm sensitivity level entry from JSON `get.alarm.detailInfo`."""

    level_id: int | None = None
    value: int | None = None


@dataclass(frozen=True)
class DeviceAlarmRegionInfo:
    """Alarm detection region reported by JSON `get.alarm.detailInfo`."""

    row_num: int | None = None
    col_num: int | None = None
    data: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmSmartFilterInfo:
    """Smart-filter flags reported by JSON `get.alarm.detailInfo`."""

    peds: int | None = None
    vehc: int | None = None


@dataclass(frozen=True)
class DeviceAlarmChannelDetailInfo:
    """Per-channel alarm configuration from JSON `get.alarm.detailInfo`."""

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
    schedule: list["DevicePirScheduleDayInfo"] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceAlarmDetailInfo:
    """Alarm detail configuration reported by JSON `get.alarm.detailInfo`."""

    error: int
    alarm_type: int | None = None
    channel: DeviceAlarmChannelDetailInfo | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceAlarmStatusInfo:
    """Alarm status reported by custom JSON `get.alarm.status`."""

    error: int
    status: str = ""
    is_on: bool | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceHardwareInfo:
    """Battery and charge state reported by JSON `getHWInfo`."""

    error: int
    battery_quantity: int | None = None
    voltmeter_temperature: float | None = None
    charge_source: int | None = None
    charge_status: int | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLightItemInfo:
    """One room light reported by JSON `get.light.info`."""

    number: int | None = None
    name: str = ""
    status: int | None = None
    brightness: int | None = None


@dataclass(frozen=True)
class DeviceLightRoomInfo:
    """One light room reported by JSON `get.light.info`."""

    number: int | None = None
    name: str = ""
    lights: list[DeviceLightItemInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceLightInfo:
    """Room light state reported by JSON `get.light.info`."""

    error: int
    rooms: list[DeviceLightRoomInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DevicePirScheduleSlotInfo:
    """One PIR schedule slot reported by JSON `getPIRCfg`."""

    section: str = ""
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DevicePirScheduleDayInfo:
    """One PIR schedule day reported by JSON `getPIRCfg`."""

    week: str = ""
    week_index: int | None = None
    slots: list[DevicePirScheduleSlotInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DevicePirConfigInfo:
    """PIR sensor configuration reported by JSON `getPIRCfg`."""

    error: int
    enabled: bool | None = None
    sensitivity: int | None = None
    link_record: bool | None = None
    schedule: list[DevicePirScheduleDayInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceThirdPartyPushScheduleSlotInfo:
    """One third-party push schedule slot from `get.thirdpartypush.info`."""

    section: str = ""
    enabled: bool | None = None
    start: str = ""
    end: str = ""


@dataclass(frozen=True)
class DeviceThirdPartyPushScheduleDayInfo:
    """One third-party push schedule day from `get.thirdpartypush.info`."""

    week: str = ""
    week_index: int | None = None
    slots: list[DeviceThirdPartyPushScheduleSlotInfo] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class DeviceThirdPartyPushInfo:
    """Third-party alarm push settings reported by JSON `get.thirdpartypush.info`."""

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
    """FPS mode reported by JSON `get.fps.mode`."""

    error: int
    mode: int | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceBabysitterStateInfo:
    """Babysitter mode state reported by `get.babysitter`."""

    error: int
    mode: bool | None = None
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceLockTimeInfo:
    """Unlock time range reported for one lock by `get.lock.status`."""

    min: float | None = None
    max: float | None = None
    current: float | None = None


@dataclass(frozen=True)
class DeviceLockInfo:
    """One lock entry reported by JSON `get.lock.status`."""

    lock_id: int | None = None
    name: str = ""
    time: DeviceLockTimeInfo | None = None


@dataclass(frozen=True)
class DeviceLockStatusInfo:
    """Lock configuration/status reported by `get.lock.status`."""

    error: int
    locks: list[DeviceLockInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceCityCoordinateInfo:
    """City coordinates and sun times from custom JSON `get.city.coordinate`."""

    error: int
    latitude: float | None = None
    longitude: float | None = None
    sunrise: str = ""
    sunset: str = ""
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFloodlightInfo:
    """One floodlight entry reported by JSON `get.floodlight.switch`."""

    code: str = ""
    status: str = ""
    status_code: int | None = None
    brightness: int | None = None
    duration: int | None = None


@dataclass(frozen=True)
class DeviceFloodlightSwitchInfo:
    """Floodlight switch state reported by `get.floodlight.switch`."""

    error: int
    lights: list[DeviceFloodlightInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceFloodlightScheduleTimeInfo:
    """One floodlight schedule time entry from `get.floodlight.schedule`."""

    mode: str = ""
    mode_code: int | None = None
    shift: int | None = None
    time: str = ""


@dataclass(frozen=True)
class DeviceFloodlightSchedulePlanInfo:
    """One floodlight schedule plan from `get.floodlight.schedule`."""

    number: int | None = None
    enabled: bool | None = None
    start: DeviceFloodlightScheduleTimeInfo | None = None
    end: DeviceFloodlightScheduleTimeInfo | None = None


@dataclass(frozen=True)
class DeviceFloodlightScheduleDayInfo:
    """One floodlight schedule day from `get.floodlight.schedule`."""

    week: int | None = None
    plans: list[DeviceFloodlightSchedulePlanInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceFloodlightScheduleInfo:
    """Floodlight schedule reported by custom JSON `get.floodlight.schedule`."""

    error: int
    sunrise: str = ""
    sunset: str = ""
    days: list[DeviceFloodlightScheduleDayInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceVoiceFileInfo:
    """One voice prompt file reported by `get.voice.message`."""

    file_id: int | None = None
    name: str = ""


@dataclass(frozen=True)
class DeviceVoiceMessageInfo:
    """Voice-message settings reported by `get.voice.message`."""

    error: int
    current_file_id: int | None = None
    mode: str = ""
    mode_code: int | None = None
    files: list[DeviceVoiceFileInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None


@dataclass(frozen=True)
class DeviceSmartSwitchChannelInfo:
    """One smart-switch channel reported by JSON `get.smartswitch.info`."""

    number: int | None = None
    name: str = ""
    state: bool | None = None


@dataclass(frozen=True)
class DeviceSmartSwitchItemInfo:
    """One smart switch reported by JSON `get.smartswitch.info`."""

    number: int | None = None
    name: str = ""
    online: bool | None = None
    switch_channel_total: int | None = None
    channels: list[DeviceSmartSwitchChannelInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceSmartSwitchRoomInfo:
    """One smart-switch room reported by JSON `get.smartswitch.info`."""

    number: int | None = None
    name: str = ""
    switches: list[DeviceSmartSwitchItemInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceSmartSwitchInfo:
    """Smart-switch topology reported by JSON `get.smartswitch.info`."""

    error: int
    add_status: int | None = None
    rooms: list[DeviceSmartSwitchRoomInfo] = field(default_factory=list)
    raw: DeviceJsonCgiResponse | None = None

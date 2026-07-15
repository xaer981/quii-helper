"""Parsing helpers for read-only JSON `/tdkcgi` responses."""

from __future__ import annotations

from typing import Any

from quii_helper.device.json_cgi.models import (
    DeviceAlarmChannelDetailInfo,
    DeviceAlarmDetailInfo,
    DeviceAlarmIntervalInfo,
    DeviceAlarmLevelInfo,
    DeviceAlarmRegionInfo,
    DeviceAlarmSmartFilterInfo,
    DeviceAlarmStatusInfo,
    DeviceAudioSessionInfo,
    DeviceAudioVolumeInfo,
    DeviceAudioVolumeRange,
    DeviceBabysitterStateInfo,
    DeviceCityCoordinateInfo,
    DeviceFloodlightInfo,
    DeviceFloodlightScheduleDayInfo,
    DeviceFloodlightScheduleInfo,
    DeviceFloodlightSchedulePlanInfo,
    DeviceFloodlightScheduleTimeInfo,
    DeviceFloodlightSwitchInfo,
    DeviceHardwareInfo,
    DeviceJsonCgiResponse,
    DeviceJsonFpsModeInfo,
    DeviceLightInfo,
    DeviceLightItemInfo,
    DeviceLightRoomInfo,
    DeviceLockInfo,
    DeviceLockStatusInfo,
    DeviceLockTimeInfo,
    DevicePirConfigInfo,
    DevicePirScheduleDayInfo,
    DevicePirScheduleSlotInfo,
    DeviceSmartSwitchChannelInfo,
    DeviceSmartSwitchInfo,
    DeviceSmartSwitchItemInfo,
    DeviceSmartSwitchRoomInfo,
    DeviceThirdPartyPushInfo,
    DeviceThirdPartyPushScheduleDayInfo,
    DeviceThirdPartyPushScheduleSlotInfo,
    DeviceVoiceFileInfo,
    DeviceVoiceMessageInfo,
)

FLOODLIGHT_STATUS_ON = 0
FLOODLIGHT_STATUS_OFF = 1
FLOODLIGHT_STATUS_AUTO = 2

FLOODLIGHT_SCHEDULE_TIME_MODE_SUNRISE = 0
FLOODLIGHT_SCHEDULE_TIME_MODE_SUNSET = 1
FLOODLIGHT_SCHEDULE_TIME_MODE_FIXED = 2
FLOODLIGHT_SCHEDULE_TIME_MODE_UNKNOWN = -1

VOICE_MODE_AUTO = 0
VOICE_MODE_MANUAL = 1

CHARGE_SOURCE_NONE = 0
CHARGE_SOURCE_5V = 1
CHARGE_SOURCE_9V = 2
CHARGE_SOURCE_SOLAR_PANEL = 3
CHARGE_SOURCE_UNKNOWN = -1

CHARGE_STATUS_DISCHARGE = 0
CHARGE_STATUS_CHARGE = 1

WEEK_INDEX_BY_NAME = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_json_cgi_response(
    command: str,
    raw: dict[str, Any],
) -> DeviceJsonCgiResponse:
    """Parse a native JSON CGI response envelope."""

    body = _as_dict(raw.get("body"))
    content = _as_dict(body.get("content"))
    return DeviceJsonCgiResponse(
        command=command,
        error=_to_int(body.get("error"), default=-1) or 0,
        content=content,
        raw=raw,
    )


def parse_audio_volume_info(
    response: DeviceJsonCgiResponse,
) -> DeviceAudioVolumeInfo:
    """Map `get.audio.outvolume` content into `DeviceAudioVolumeInfo`."""

    return DeviceAudioVolumeInfo(
        error=response.error,
        prompt=_parse_volume_range(response.content.get("prompt")),
        talk=_parse_volume_range(response.content.get("talk")),
        raw=response,
    )


def parse_audio_session_info(
    response: DeviceJsonCgiResponse,
) -> DeviceAudioSessionInfo:
    """Map `get.audio.session` content into `DeviceAudioSessionInfo`."""

    return DeviceAudioSessionInfo(
        error=response.error,
        session=_to_str(response.content.get("session")),
        file_id=_to_str(response.content.get("fileid")),
        raw=response,
    )


def parse_alarm_detail_info(
    response: DeviceJsonCgiResponse,
) -> DeviceAlarmDetailInfo:
    """Map `get.alarm.detailInfo` content into `DeviceAlarmDetailInfo`."""

    config = _as_dict(response.content.get("config"))
    return DeviceAlarmDetailInfo(
        error=response.error,
        alarm_type=_to_int(response.content.get("alarmtype")),
        channel=_parse_alarm_channel_detail_info(config.get("channel")),
        raw=response,
    )


def parse_alarm_status_info(
    response: DeviceJsonCgiResponse,
) -> DeviceAlarmStatusInfo:
    """Map `get.alarm.status` content into `DeviceAlarmStatusInfo`."""

    status = _to_str(response.content.get("status"))
    return DeviceAlarmStatusInfo(
        error=response.error,
        status=status,
        is_on=_alarm_status_is_on(status),
        raw=response,
    )


def parse_hardware_info(
    response: DeviceJsonCgiResponse,
) -> DeviceHardwareInfo:
    """Map `getHWInfo` content into `DeviceHardwareInfo`."""

    voltmeter_temp = _to_int(response.content.get("voltameterTemp"))
    return DeviceHardwareInfo(
        error=response.error,
        battery_quantity=_to_int(response.content.get("batQuantity")),
        voltmeter_temperature=(
            None if voltmeter_temp is None else voltmeter_temp / 10.0
        ),
        charge_source=_normalize_charge_source(
            _to_int(response.content.get("chargeSource"))
        ),
        charge_status=_normalize_charge_status(
            _to_int(response.content.get("chargeStatus"))
        ),
        raw=response,
    )


def parse_light_info(
    response: DeviceJsonCgiResponse,
) -> DeviceLightInfo:
    """Map `get.light.info` content into `DeviceLightInfo`."""

    return DeviceLightInfo(
        error=response.error,
        rooms=[
            _parse_light_room_info(item)
            for item in _as_list(response.content.get("room"))
        ],
        raw=response,
    )


def parse_json_fps_mode_info(
    response: DeviceJsonCgiResponse,
) -> DeviceJsonFpsModeInfo:
    """Map `get.fps.mode` content into `DeviceJsonFpsModeInfo`."""

    return DeviceJsonFpsModeInfo(
        error=response.error,
        mode=_to_int(response.content.get("mode")),
        raw=response,
    )


def parse_pir_config_info(
    response: DeviceJsonCgiResponse,
) -> DevicePirConfigInfo:
    """Map `getPIRCfg` content into `DevicePirConfigInfo`."""

    return DevicePirConfigInfo(
        error=response.error,
        enabled=_to_nonzero_bool(response.content.get("enabled")),
        sensitivity=_to_int(response.content.get("sensitivity")),
        link_record=_to_nonzero_bool(response.content.get("linkRecord")),
        schedule=[
            _parse_pir_schedule_day_info(item)
            for item in _as_list(response.content.get("schedule"))
        ],
        raw=response,
    )


def parse_third_party_push_info(
    response: DeviceJsonCgiResponse,
) -> DeviceThirdPartyPushInfo:
    """Map `get.thirdpartypush.info` content into `DeviceThirdPartyPushInfo`."""

    return DeviceThirdPartyPushInfo(
        error=response.error,
        account=_to_str(response.content.get("account")),
        area_code=_to_str(response.content.get("areacode")),
        push_enabled=_to_nonzero_bool(response.content.get("pushenable")),
        third_party_type=_to_int(response.content.get("thirdpartytype")),
        upload_type=_to_int(response.content.get("uploadtype")),
        event_types=_to_int_list(response.content.get("eventtype")),
        supported_event_types=_to_int_list(
            response.content.get("supporteventtype")
        ),
        schedule=[
            _parse_third_party_push_schedule_day_info(item)
            for item in _as_list(response.content.get("schedule"))
        ],
        raw=response,
    )


def parse_babysitter_state_info(
    response: DeviceJsonCgiResponse,
) -> DeviceBabysitterStateInfo:
    """Map `get.babysitter` content into `DeviceBabysitterStateInfo`."""

    return DeviceBabysitterStateInfo(
        error=response.error,
        mode=_to_bool(response.content.get("mode")),
        raw=response,
    )


def parse_lock_status_info(
    response: DeviceJsonCgiResponse,
) -> DeviceLockStatusInfo:
    """Map `get.lock.status` content into `DeviceLockStatusInfo`."""

    return DeviceLockStatusInfo(
        error=response.error,
        locks=[
            _parse_lock_info(item)
            for item in _as_list(response.content.get("lock"))
        ],
        raw=response,
    )


def parse_city_coordinate_info(
    response: DeviceJsonCgiResponse,
) -> DeviceCityCoordinateInfo:
    """Map `get.city.coordinate` into `DeviceCityCoordinateInfo`."""

    coordinate = _as_dict(response.content.get("coordinate"))
    sun_time = _as_dict(response.content.get("suntime"))
    return DeviceCityCoordinateInfo(
        error=response.error,
        latitude=_to_float(coordinate.get("latitude")),
        longitude=_to_float(coordinate.get("longitude")),
        sunrise=_to_str(sun_time.get("sunrise")),
        sunset=_to_str(sun_time.get("sunset")),
        raw=response,
    )


def parse_floodlight_switch_info(
    response: DeviceJsonCgiResponse,
) -> DeviceFloodlightSwitchInfo:
    """Map `get.floodlight.switch` content into `DeviceFloodlightSwitchInfo`."""

    return DeviceFloodlightSwitchInfo(
        error=response.error,
        lights=[
            _parse_floodlight_info(item)
            for item in _as_list(response.content.get("light"))
        ],
        raw=response,
    )


def parse_floodlight_schedule_info(
    response: DeviceJsonCgiResponse,
) -> DeviceFloodlightScheduleInfo:
    """Map `get.floodlight.schedule` into `DeviceFloodlightScheduleInfo`."""

    sun_time = _as_dict(response.content.get("suntime"))
    schedule = _as_dict(response.content.get("schedule"))
    return DeviceFloodlightScheduleInfo(
        error=response.error,
        sunrise=_to_str(sun_time.get("sunrise")),
        sunset=_to_str(sun_time.get("sunset")),
        days=[
            _parse_floodlight_schedule_day_info(item)
            for item in _as_list(schedule.get("day"))
        ],
        raw=response,
    )


def parse_voice_message_info(
    response: DeviceJsonCgiResponse,
) -> DeviceVoiceMessageInfo:
    """Map `get.voice.message` content into `DeviceVoiceMessageInfo`."""

    mode = _to_str(response.content.get("mode"))
    return DeviceVoiceMessageInfo(
        error=response.error,
        current_file_id=_to_int(response.content.get("currenrVoiceFileid")),
        mode=mode,
        mode_code=_voice_mode_code(mode),
        files=[
            _parse_voice_file_info(item)
            for item in _as_list(response.content.get("filelist"))
        ],
        raw=response,
    )


def parse_smart_switch_info(
    response: DeviceJsonCgiResponse,
) -> DeviceSmartSwitchInfo:
    """Map `get.smartswitch.info` content into `DeviceSmartSwitchInfo`."""

    return DeviceSmartSwitchInfo(
        error=response.error,
        add_status=_to_int(response.content.get("add_status")),
        rooms=[
            _parse_smart_switch_room_info(item)
            for item in _as_list(response.content.get("room"))
        ],
        raw=response,
    )


def _parse_volume_range(value: object) -> DeviceAudioVolumeRange | None:
    item = _as_dict(value)
    if not item:
        return None
    return DeviceAudioVolumeRange(
        level=_to_int(item.get("level")),
        min_level=_to_int(item.get("min_level")),
        max_level=_to_int(item.get("max_level")),
    )


def _parse_alarm_channel_detail_info(
    value: object,
) -> DeviceAlarmChannelDetailInfo | None:
    item = _as_dict(value)
    if not item:
        return None
    return DeviceAlarmChannelDetailInfo(
        channel_id=_to_int(item.get("id")),
        enabled=_to_nonzero_bool(item.get("enabled")),
        sensitivity=_to_int(item.get("sensitivity")),
        max_sensitivity=_to_int(item.get("max_sensitivity")),
        move_enabled=_to_nonzero_bool(item.get("move_enabled")),
        record_enabled=_to_nonzero_bool(item.get("record_enabled")),
        alarm_light_enabled=_to_nonzero_bool(item.get("alarmlight_enabled")),
        whistle_enabled=_to_nonzero_bool(item.get("whistle_enabled")),
        only_track=_to_nonzero_bool(item.get("only_track")),
        record_latch=_to_int(item.get("record_latch")),
        schedule_mode=_to_str(item.get("schedule_mode")),
        interval=_parse_alarm_interval_info(item.get("interval")),
        levels=[
            _parse_alarm_level_info(level)
            for level in _as_list(item.get("levellist"))
        ],
        region=_parse_alarm_region_info(item.get("region")),
        smart_filter=_parse_alarm_smart_filter_info(item.get("smart_filter")),
        schedule=[
            _parse_pir_schedule_day_info(day)
            for day in _as_list(item.get("schedule"))
        ],
    )


def _parse_alarm_interval_info(
    value: object,
) -> DeviceAlarmIntervalInfo | None:
    item = _as_dict(value)
    if not item:
        return None
    return DeviceAlarmIntervalInfo(
        value=_to_int(item.get("value")),
        range=[
            parsed
            for parsed in (_to_int(raw) for raw in _as_list(item.get("range")))
            if parsed is not None
        ],
    )


def _parse_alarm_level_info(value: object) -> DeviceAlarmLevelInfo:
    item = _as_dict(value)
    return DeviceAlarmLevelInfo(
        level_id=_to_int(item.get("id")),
        value=_to_int(item.get("value")),
    )


def _parse_alarm_region_info(value: object) -> DeviceAlarmRegionInfo | None:
    item = _as_dict(value)
    if not item:
        return None
    return DeviceAlarmRegionInfo(
        row_num=_to_int(item.get("rownum")),
        col_num=_to_int(item.get("colnum")),
        data=[
            _to_str(_as_dict(region_item).get("data"))
            for region_item in _as_list(item.get("datalist"))
        ],
    )


def _parse_alarm_smart_filter_info(
    value: object,
) -> DeviceAlarmSmartFilterInfo | None:
    item = _as_dict(value)
    if not item:
        return None
    return DeviceAlarmSmartFilterInfo(
        peds=_to_int(item.get("peds")),
        vehc=_to_int(item.get("vehc")),
    )


def _parse_light_room_info(value: object) -> DeviceLightRoomInfo:
    item = _as_dict(value)
    return DeviceLightRoomInfo(
        number=_to_int(item.get("number")),
        name=_to_str(item.get("name")),
        lights=[
            _parse_light_item_info(light)
            for light in _as_list(item.get("lights"))
        ],
    )


def _parse_light_item_info(value: object) -> DeviceLightItemInfo:
    item = _as_dict(value)
    return DeviceLightItemInfo(
        number=_to_int(item.get("number")),
        name=_to_str(item.get("name")),
        status=_to_int(item.get("status")),
        brightness=_to_int(item.get("brightness")),
    )


def _parse_pir_schedule_day_info(
    value: object,
) -> DevicePirScheduleDayInfo:
    item = _as_dict(value)
    week = _to_str(item.get("week"))
    return DevicePirScheduleDayInfo(
        week=week,
        week_index=_week_index(week),
        slots=[
            _parse_pir_schedule_slot_info(slot)
            for slot in _as_list(item.get("time"))
        ],
    )


def _parse_pir_schedule_slot_info(
    value: object,
) -> DevicePirScheduleSlotInfo:
    item = _as_dict(value)
    return DevicePirScheduleSlotInfo(
        section=_to_str(item.get("section")),
        enabled=_to_nonzero_bool(item.get("enabled")),
        start=_to_str(item.get("start")),
        end=_to_str(item.get("end")),
    )


def _parse_third_party_push_schedule_day_info(
    value: object,
) -> DeviceThirdPartyPushScheduleDayInfo:
    item = _as_dict(value)
    week = _to_str(item.get("week"))
    return DeviceThirdPartyPushScheduleDayInfo(
        week=week,
        week_index=_week_index(week),
        slots=[
            _parse_third_party_push_schedule_slot_info(slot)
            for slot in _as_list(item.get("time"))
        ],
    )


def _parse_third_party_push_schedule_slot_info(
    value: object,
) -> DeviceThirdPartyPushScheduleSlotInfo:
    item = _as_dict(value)
    return DeviceThirdPartyPushScheduleSlotInfo(
        section=_to_str(item.get("section")),
        enabled=_to_nonzero_bool(item.get("enabled")),
        start=_to_str(item.get("start")),
        end=_to_str(item.get("end")),
    )


def _parse_lock_info(value: object) -> DeviceLockInfo:
    item = _as_dict(value)
    time = _as_dict(item.get("time"))
    return DeviceLockInfo(
        lock_id=_to_int(item.get("id")),
        name=_to_str(item.get("name")),
        time=(
            None
            if not time
            else DeviceLockTimeInfo(
                min=_to_float(time.get("min")),
                max=_to_float(time.get("max")),
                current=_to_float(time.get("value")),
            )
        ),
    )


def _parse_floodlight_info(value: object) -> DeviceFloodlightInfo:
    item = _as_dict(value)
    status = _to_str(item.get("status"))
    return DeviceFloodlightInfo(
        code=_to_str(item.get("code")),
        status=status,
        status_code=_floodlight_status_code(status),
        brightness=_to_int(item.get("brightness")),
        duration=_to_int(item.get("duration")),
    )


def _parse_floodlight_schedule_day_info(
    value: object,
) -> DeviceFloodlightScheduleDayInfo:
    item = _as_dict(value)
    return DeviceFloodlightScheduleDayInfo(
        week=_to_int(item.get("week")),
        plans=[
            _parse_floodlight_schedule_plan_info(plan)
            for plan in _as_list(item.get("plan"))
        ],
    )


def _parse_floodlight_schedule_plan_info(
    value: object,
) -> DeviceFloodlightSchedulePlanInfo:
    item = _as_dict(value)
    enabled = _to_bool(item.get("enable"))
    start: DeviceFloodlightScheduleTimeInfo | None
    end: DeviceFloodlightScheduleTimeInfo | None
    if enabled is False:
        start = _cleared_floodlight_schedule_time_info()
        end = _cleared_floodlight_schedule_time_info()
    else:
        start = _parse_floodlight_schedule_time_info(item.get("start"))
        end = _parse_floodlight_schedule_time_info(item.get("end"))
    return DeviceFloodlightSchedulePlanInfo(
        number=_to_int(item.get("num")),
        enabled=enabled,
        start=start,
        end=end,
    )


def _parse_floodlight_schedule_time_info(
    value: object,
) -> DeviceFloodlightScheduleTimeInfo | None:
    item = _as_dict(value)
    if not item:
        return None
    mode = _to_str(item.get("mode"))
    return DeviceFloodlightScheduleTimeInfo(
        mode=mode,
        mode_code=_floodlight_schedule_time_mode_code(mode),
        shift=_to_int(item.get("shift")),
        time=_to_str(item.get("time")),
    )


def _cleared_floodlight_schedule_time_info() -> (
    DeviceFloodlightScheduleTimeInfo
):
    return DeviceFloodlightScheduleTimeInfo(
        mode="time",
        mode_code=FLOODLIGHT_SCHEDULE_TIME_MODE_FIXED,
        shift=0,
        time="00:00:00",
    )


def _parse_smart_switch_room_info(value: object) -> DeviceSmartSwitchRoomInfo:
    item = _as_dict(value)
    return DeviceSmartSwitchRoomInfo(
        number=_to_int(item.get("number")),
        name=_to_str(item.get("name")),
        switches=[
            _parse_smart_switch_item_info(switch)
            for switch in _as_list(item.get("switchs"))
        ],
    )


def _parse_smart_switch_item_info(value: object) -> DeviceSmartSwitchItemInfo:
    item = _as_dict(value)
    return DeviceSmartSwitchItemInfo(
        number=_to_int(item.get("number")),
        name=_to_str(item.get("name")),
        online=_to_nonzero_bool(item.get("online")),
        switch_channel_total=_to_int(item.get("switchchntotal")),
        channels=[
            _parse_smart_switch_channel_info(channel)
            for channel in _as_list(item.get("switchchn"))
        ],
    )


def _parse_smart_switch_channel_info(
    value: object,
) -> DeviceSmartSwitchChannelInfo:
    item = _as_dict(value)
    return DeviceSmartSwitchChannelInfo(
        number=_to_int(item.get("number")),
        name=_to_str(item.get("name")),
        state=_to_nonzero_bool(item.get("state")),
    )


def _parse_voice_file_info(value: object) -> DeviceVoiceFileInfo:
    item = _as_dict(value)
    return DeviceVoiceFileInfo(
        file_id=_to_int(item.get("fileid")),
        name=_to_str(item.get("name")),
    )


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _to_str(value: object, default: str = "") -> str:
    return default if value is None else str(value)


def _to_int(value: object, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str | bytes | bytearray):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_int_list(value: object) -> list[int]:
    return [
        parsed
        for parsed in (_to_int(item) for item in _as_list(value))
        if parsed is not None
    ]


def _to_float(value: object, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str | bytes | bytearray):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "on", "yes"}:
            return True
        if normalized in {"false", "0", "off", "no"}:
            return False
    return None


def _to_nonzero_bool(value: object) -> bool | None:
    numeric = _to_int(value)
    if numeric is not None:
        return numeric != 0
    return _to_bool(value)


def _floodlight_status_code(status: str) -> int | None:
    return {
        "on": FLOODLIGHT_STATUS_ON,
        "off": FLOODLIGHT_STATUS_OFF,
        "auto": FLOODLIGHT_STATUS_AUTO,
    }.get(status.strip().lower())


def _floodlight_schedule_time_mode_code(mode: str) -> int:
    return {
        "sunrise": FLOODLIGHT_SCHEDULE_TIME_MODE_SUNRISE,
        "sunset": FLOODLIGHT_SCHEDULE_TIME_MODE_SUNSET,
        "time": FLOODLIGHT_SCHEDULE_TIME_MODE_FIXED,
    }.get(mode.strip().lower(), FLOODLIGHT_SCHEDULE_TIME_MODE_UNKNOWN)


def _voice_mode_code(mode: str) -> int | None:
    return {
        "auto": VOICE_MODE_AUTO,
        "manul": VOICE_MODE_MANUAL,
        "manual": VOICE_MODE_MANUAL,
    }.get(mode.strip().lower())


def _alarm_status_is_on(status: str) -> bool | None:
    normalized = status.strip().lower()
    if normalized == "on":
        return True
    if normalized in {"off", "auto"}:
        return False
    return None


def _normalize_charge_source(value: int | None) -> int | None:
    if value is None:
        return None
    if value in {
        CHARGE_SOURCE_NONE,
        CHARGE_SOURCE_5V,
        CHARGE_SOURCE_9V,
        CHARGE_SOURCE_SOLAR_PANEL,
    }:
        return value
    return CHARGE_SOURCE_UNKNOWN


def _normalize_charge_status(value: int | None) -> int | None:
    if value is None:
        return None
    if value == CHARGE_STATUS_CHARGE:
        return CHARGE_STATUS_CHARGE
    return CHARGE_STATUS_DISCHARGE


def _week_index(week: str) -> int | None:
    return WEEK_INDEX_BY_NAME.get(week.strip().lower())

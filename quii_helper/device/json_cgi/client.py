"""Read-only JSON client helpers for the device `/tdkcgi` endpoint."""

from typing import Any

from quii_helper.device.cgi import DEFAULT_CGI_HTTP_PORT, DEFAULT_CGI_USERNAME
from quii_helper.device.http.transport import request_json_cgi
from quii_helper.device.json_cgi.models import (
    DeviceAlarmDetailInfo,
    DeviceAlarmStatusInfo,
    DeviceAudioSessionInfo,
    DeviceAudioVolumeInfo,
    DeviceBabysitterStateInfo,
    DeviceCityCoordinateInfo,
    DeviceFloodlightScheduleInfo,
    DeviceFloodlightSwitchInfo,
    DeviceHardwareInfo,
    DeviceJsonCgiResponse,
    DeviceJsonFpsModeInfo,
    DeviceLightInfo,
    DeviceLockStatusInfo,
    DevicePirConfigInfo,
    DeviceSmartSwitchInfo,
    DeviceThirdPartyPushInfo,
    DeviceVoiceMessageInfo,
)
from quii_helper.device.json_cgi.parser import (
    parse_alarm_detail_info,
    parse_alarm_status_info,
    parse_audio_session_info,
    parse_audio_volume_info,
    parse_babysitter_state_info,
    parse_city_coordinate_info,
    parse_floodlight_schedule_info,
    parse_floodlight_switch_info,
    parse_hardware_info,
    parse_json_cgi_response,
    parse_json_fps_mode_info,
    parse_light_info,
    parse_lock_status_info,
    parse_pir_config_info,
    parse_smart_switch_info,
    parse_third_party_push_info,
    parse_voice_message_info,
)
from quii_helper.device.security.auth import encode_device_password

COMMAND_GET_ALARM_DETAIL_INFO = "get.alarm.detailInfo"
COMMAND_GET_ALARM_STATUS = "get.alarm.status"
COMMAND_GET_AUDIO_SESSION = "get.audio.session"
COMMAND_GET_AUDIO_VOLUME = "get.audio.outvolume"
COMMAND_GET_BABYSITTER_STATE = "get.babysitter"
COMMAND_GET_CITY_COORDINATE = "get.city.coordinate"
COMMAND_GET_FLOODLIGHT_SCHEDULE = "get.floodlight.schedule"
COMMAND_GET_FLOODLIGHT_SWITCH = "get.floodlight.switch"
COMMAND_GET_HARDWARE = "getHWInfo"
COMMAND_GET_JSON_FPS_MODE = "get.fps.mode"
COMMAND_GET_LIGHT_INFO = "get.light.info"
COMMAND_GET_LOCK_STATUS = "get.lock.status"
COMMAND_GET_PIR_CONFIG = "getPIRCfg"
COMMAND_GET_SMART_SWITCH_INFO = "get.smartswitch.info"
COMMAND_GET_THIRD_PARTY_PUSH_INFO = "get.thirdpartypush.info"
COMMAND_GET_VOICE_MESSAGE = "get.voice.message"


def request_readonly_json_cgi(
    command: str,
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    username: str = DEFAULT_CGI_USERNAME,
    content: dict[str, Any] | None = None,
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceJsonCgiResponse:
    """Request a read-only JSON CGI command using the native LAN header."""

    result: dict[str, Any] = request_json_cgi(
        command,
        host=host,
        port=port,
        username=username,
        password=encode_device_password(auth_code),
        encrypted=False,
        scheme=scheme,
        passwordencode=1,
        content=content,
        verify_tls=verify_tls,
        debug=debug,
    )
    return parse_json_cgi_response(command, result["raw"])


def request_alarm_detail_info(
    *,
    host: str,
    auth_code: str,
    alarm_type: int,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmDetailInfo:
    """Fetch JSON `get.alarm.detailInfo` from `/tdkcgi`."""

    return parse_alarm_detail_info(
        request_readonly_json_cgi(
            COMMAND_GET_ALARM_DETAIL_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            content={"alarmtype": alarm_type},
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_alarm_status_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmStatusInfo:
    """Fetch JSON `get.alarm.status` from `/tdkcgi`."""

    return parse_alarm_status_info(
        request_readonly_json_cgi(
            COMMAND_GET_ALARM_STATUS,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_audio_session_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAudioSessionInfo:
    """Fetch JSON `get.audio.session` from `/tdkcgi`."""

    return parse_audio_session_info(
        request_readonly_json_cgi(
            COMMAND_GET_AUDIO_SESSION,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_audio_volume_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAudioVolumeInfo:
    """Fetch JSON `get.audio.outvolume` from `/tdkcgi`."""

    return parse_audio_volume_info(
        request_readonly_json_cgi(
            COMMAND_GET_AUDIO_VOLUME,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_hardware_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceHardwareInfo:
    """Fetch JSON `getHWInfo` from `/tdkcgi`."""

    return parse_hardware_info(
        request_readonly_json_cgi(
            COMMAND_GET_HARDWARE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_light_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceLightInfo:
    """Fetch JSON `get.light.info` from `/tdkcgi`."""

    return parse_light_info(
        request_readonly_json_cgi(
            COMMAND_GET_LIGHT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_json_fps_mode_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceJsonFpsModeInfo:
    """Fetch JSON `get.fps.mode` from `/tdkcgi`."""

    return parse_json_fps_mode_info(
        request_readonly_json_cgi(
            COMMAND_GET_JSON_FPS_MODE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_babysitter_state_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceBabysitterStateInfo:
    """Fetch JSON `get.babysitter` from `/tdkcgi`."""

    return parse_babysitter_state_info(
        request_readonly_json_cgi(
            COMMAND_GET_BABYSITTER_STATE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_pir_config_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DevicePirConfigInfo:
    """Fetch JSON `getPIRCfg` from `/tdkcgi`."""

    return parse_pir_config_info(
        request_readonly_json_cgi(
            COMMAND_GET_PIR_CONFIG,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_third_party_push_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceThirdPartyPushInfo:
    """Fetch JSON `get.thirdpartypush.info` from `/tdkcgi`."""

    return parse_third_party_push_info(
        request_readonly_json_cgi(
            COMMAND_GET_THIRD_PARTY_PUSH_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_smart_switch_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceSmartSwitchInfo:
    """Fetch JSON `get.smartswitch.info` from `/tdkcgi`."""

    return parse_smart_switch_info(
        request_readonly_json_cgi(
            COMMAND_GET_SMART_SWITCH_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_lock_status_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceLockStatusInfo:
    """Fetch JSON `get.lock.status` from `/tdkcgi`."""

    return parse_lock_status_info(
        request_readonly_json_cgi(
            COMMAND_GET_LOCK_STATUS,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_floodlight_switch_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceFloodlightSwitchInfo:
    """Fetch JSON `get.floodlight.switch` from `/tdkcgi`."""

    return parse_floodlight_switch_info(
        request_readonly_json_cgi(
            COMMAND_GET_FLOODLIGHT_SWITCH,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_city_coordinate_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceCityCoordinateInfo:
    """Fetch JSON `get.city.coordinate` from `/tdkcgi`."""

    return parse_city_coordinate_info(
        request_readonly_json_cgi(
            COMMAND_GET_CITY_COORDINATE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_floodlight_schedule_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceFloodlightScheduleInfo:
    """Fetch JSON `get.floodlight.schedule` from `/tdkcgi`."""

    return parse_floodlight_schedule_info(
        request_readonly_json_cgi(
            COMMAND_GET_FLOODLIGHT_SCHEDULE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_voice_message_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceVoiceMessageInfo:
    """Fetch JSON `get.voice.message` from `/tdkcgi`."""

    return parse_voice_message_info(
        request_readonly_json_cgi(
            COMMAND_GET_VOICE_MESSAGE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )

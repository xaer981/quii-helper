"""Camera-level read-only JSON CGI service."""

from quii_helper.camera.device_cgi import DeviceCgiEndpoint
from quii_helper.device.json_cgi import (
    DeviceAlarmDetailInfo,
    DeviceAlarmStatusInfo,
    DeviceAudioSessionInfo,
    DeviceAudioVolumeInfo,
    DeviceBabysitterStateInfo,
    DeviceCityCoordinateInfo,
    DeviceFloodlightScheduleInfo,
    DeviceFloodlightSwitchInfo,
    DeviceHardwareInfo,
    DeviceJsonFpsModeInfo,
    DeviceLightInfo,
    DeviceLockStatusInfo,
    DevicePirConfigInfo,
    DeviceSmartSwitchInfo,
    DeviceThirdPartyPushInfo,
    DeviceVoiceMessageInfo,
    request_alarm_detail_info,
    request_alarm_status_info,
    request_audio_session_info,
    request_audio_volume_info,
    request_babysitter_state_info,
    request_city_coordinate_info,
    request_floodlight_schedule_info,
    request_floodlight_switch_info,
    request_hardware_info,
    request_json_fps_mode_info,
    request_light_info,
    request_lock_status_info,
    request_pir_config_info,
    request_smart_switch_info,
    request_third_party_push_info,
    request_voice_message_info,
)


def fetch_alarm_detail_info(
    endpoint: DeviceCgiEndpoint,
    *,
    alarm_type: int,
) -> DeviceAlarmDetailInfo:
    """Fetch read-only alarm detail configuration via JSON `/tdkcgi`."""

    return request_alarm_detail_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        alarm_type=alarm_type,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_status_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceAlarmStatusInfo:
    """Fetch read-only alarm status via custom JSON `/tdkcgi`."""

    return request_alarm_status_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_audio_session_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceAudioSessionInfo:
    """Fetch read-only audio file session via JSON `/tdkcgi`."""

    return request_audio_session_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_audio_volume_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceAudioVolumeInfo:
    """Fetch read-only audio volume via JSON `/tdkcgi`."""

    return request_audio_volume_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_hardware_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceHardwareInfo:
    """Fetch read-only hardware state via JSON `/tdkcgi`."""

    return request_hardware_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_light_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceLightInfo:
    """Fetch read-only room-light state via JSON `/tdkcgi`."""

    return request_light_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_json_fps_mode_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceJsonFpsModeInfo:
    """Fetch read-only FPS mode via JSON `/tdkcgi`."""

    return request_json_fps_mode_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_pir_config_info(
    endpoint: DeviceCgiEndpoint,
) -> DevicePirConfigInfo:
    """Fetch read-only PIR sensor configuration via JSON `/tdkcgi`."""

    return request_pir_config_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_third_party_push_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceThirdPartyPushInfo:
    """Fetch read-only third-party push settings via JSON `/tdkcgi`."""

    return request_third_party_push_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_smart_switch_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceSmartSwitchInfo:
    """Fetch read-only smart-switch topology via JSON `/tdkcgi`."""

    return request_smart_switch_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_babysitter_state_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceBabysitterStateInfo:
    """Fetch read-only babysitter state via JSON `/tdkcgi`."""

    return request_babysitter_state_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_lock_status_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceLockStatusInfo:
    """Fetch read-only lock status via JSON `/tdkcgi`."""

    return request_lock_status_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_city_coordinate_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceCityCoordinateInfo:
    """Fetch read-only city coordinates via custom JSON `/tdkcgi`."""

    return request_city_coordinate_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_floodlight_switch_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceFloodlightSwitchInfo:
    """Fetch read-only floodlight switch state via JSON `/tdkcgi`."""

    return request_floodlight_switch_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_floodlight_schedule_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceFloodlightScheduleInfo:
    """Fetch read-only floodlight schedule via JSON `/tdkcgi`."""

    return request_floodlight_schedule_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_voice_message_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceVoiceMessageInfo:
    """Fetch read-only voice-message settings via JSON `/tdkcgi`."""

    return request_voice_message_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )

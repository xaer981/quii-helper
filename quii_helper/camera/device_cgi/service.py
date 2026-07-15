"""Camera-level read-only device CGI service."""

from dataclasses import dataclass

from quii_helper.camera.device_cgi.models import (
    CameraDeviceProfile,
    command_status_for_response,
)
from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi import (
    COMMAND_GET_ALARM_CHANNEL_INFO,
    COMMAND_GET_DEVICE_ALL_INFO,
    COMMAND_GET_DEVICE_ATTACHMENT_INFO,
    COMMAND_GET_NETWORK_BASE_INFO,
    COMMAND_GET_NETWORK_INFO,
    COMMAND_GET_PRODUCT_INFO,
    COMMAND_GET_SCREEN_FLIP,
    COMMAND_GET_STORAGE_INFO,
    COMMAND_GET_SYSTEM_ABILITY,
    COMMAND_GET_SYSTEM_GENERAL,
    COMMAND_GET_TIME_INFO,
    COMMAND_GET_TIME_TITLE,
    COMMAND_GET_VIDEO_CONFIG,
    COMMAND_GET_VIDEO_SWITCH,
    COMMAND_GET_WIFI_LIST,
    DEFAULT_CGI_HTTP_PORT,
    DeviceAlarmChannelInfo,
    DeviceAlarmInputInfo,
    DeviceAlarmMotionDetectionInfo,
    DeviceAlarmScheduleInfo,
    DeviceAlarmVideoLostInfo,
    DeviceAlarmVideoShelterInfo,
    DeviceAllInfo,
    DeviceAttachmentInfo,
    DeviceCapabilitiesInfo,
    DeviceFpsInfo,
    DeviceGeneralInfo,
    DeviceHumanTraceInfo,
    DeviceMotionDetectionInfo,
    DeviceMoveDetectionInfo,
    DeviceNetworkBaseInfo,
    DeviceNetworkInfo,
    DeviceProductInfo,
    DevicePtzPresetInfo,
    DevicePtzStateInfo,
    DeviceQrCodeInfo,
    DeviceRecordAlarmInfo,
    DeviceRecordConfigInfo,
    DeviceRecordFileInfo,
    DeviceRecordListInfo,
    DeviceRecordMessageInfo,
    DeviceRecordSessionInfo,
    DeviceScreenFlipInfo,
    DeviceSmartLightInfo,
    DeviceSoundLightInfo,
    DeviceStorageInfo,
    DeviceStreamKeyInfo,
    DeviceTfCardInfo,
    DeviceTimeInfo,
    DeviceTimeTitleInfo,
    DeviceUpgradeProcessInfo,
    DeviceUpgradeStatusInfo,
    DeviceUpgradeVersionInfo,
    DeviceVideoConfigInfo,
    DeviceVideoSwitchInfo,
    DeviceWifiListInfo,
    request_alarm_channel_info,
    request_alarm_input_info,
    request_alarm_input_schedule_info,
    request_alarm_motion_detection_info,
    request_alarm_motion_detection_schedule_info,
    request_alarm_video_lost_info,
    request_alarm_video_lost_schedule_info,
    request_alarm_video_shelter_info,
    request_alarm_video_shelter_schedule_info,
    request_device_all_info,
    request_device_attachment_info,
    request_fps_info,
    request_human_trace_info,
    request_motion_detection_info,
    request_move_detection_info,
    request_network_base_info,
    request_network_info,
    request_product_info,
    request_ptz_preset_info,
    request_ptz_state_info,
    request_qr_code_info,
    request_record_alarm_info,
    request_record_config_info,
    request_record_message_info,
    request_record_session_info,
    request_screen_flip_info,
    request_smart_light_info,
    request_sound_light_info,
    request_storage_info,
    request_stream_key_info,
    request_system_capabilities,
    request_system_general_info,
    request_tf_card_info,
    request_time_info,
    request_time_title_info,
    request_upgrade_process_info,
    request_upgrade_status_info,
    request_upgrade_version_info,
    request_video_config_info,
    request_video_switch_info,
    request_wifi_list_info,
)
from quii_helper.support.errors import ConfigurationError


@dataclass(frozen=True)
class DeviceCgiEndpoint:
    """HTTP endpoint parameters for local `/tdkcgi` requests."""

    host: str
    port: int = DEFAULT_CGI_HTTP_PORT
    scheme: str = "http"
    auth_code: str = ""
    verify_tls: bool = True
    debug: bool = False


def resolve_device_cgi_endpoint(
    config: AutonomousConfig,
    *,
    port: int,
    scheme: str,
    auth_code: str | None,
    verify_tls: bool | None,
    debug: bool,
) -> DeviceCgiEndpoint:
    """Resolve local CGI endpoint settings for a `Camera` instance."""

    host = config.device_host.strip()
    if not host:
        raise ConfigurationError(
            "CAMERA_DEVICE_HOST is required for local /tdkcgi read-only "
            "requests; set CAMERA_DEVICE_HOST in .env or pass "
            "device_host=... to Camera(...)"
        )
    resolved_auth_code = auth_code
    if resolved_auth_code is None:
        resolved_auth_code = config.auth_code
    if not resolved_auth_code:
        raise ConfigurationError(
            "AUTH_CODE is required for local /tdkcgi read-only requests; "
            "set AUTH_CODE in .env, pass auth_code=... to Camera(...), or "
            "pass auth_code=... to this method"
        )
    return DeviceCgiEndpoint(
        host=host,
        port=port,
        scheme=scheme,
        auth_code=resolved_auth_code,
        verify_tls=config.tls_verify if verify_tls is None else verify_tls,
        debug=debug,
    )


def fetch_device_all_info(endpoint: DeviceCgiEndpoint) -> DeviceAllInfo:
    """Fetch read-only device status via `/tdkcgi`."""

    return request_device_all_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_channel_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceAlarmChannelInfo:
    """Fetch read-only alarm channel names via `/tdkcgi`."""

    return request_alarm_channel_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_input_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = -1,
) -> DeviceAlarmInputInfo:
    """Fetch read-only alarm input channel state via `/tdkcgi`."""

    return request_alarm_input_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_device_attachment_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceAttachmentInfo:
    """Fetch read-only sub-device attachments via `/tdkcgi`."""

    return request_device_attachment_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_motion_detection_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceMotionDetectionInfo:
    """Fetch read-only motion detection state via `/tdkcgi`."""

    return request_motion_detection_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_motion_detection_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmMotionDetectionInfo:
    """Fetch read-only alarm motion-detection state via `/tdkcgi`."""

    return request_alarm_motion_detection_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_video_lost_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmVideoLostInfo:
    """Fetch read-only video-lost alarm state via `/tdkcgi`."""

    return request_alarm_video_lost_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_video_shelter_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmVideoShelterInfo:
    """Fetch read-only video-shelter alarm state via `/tdkcgi`."""

    return request_alarm_video_shelter_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_motion_detection_schedule_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmScheduleInfo:
    """Fetch read-only motion-detection alarm schedule via `/tdkcgi`."""

    return request_alarm_motion_detection_schedule_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_video_lost_schedule_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmScheduleInfo:
    """Fetch read-only video-lost alarm schedule via `/tdkcgi`."""

    return request_alarm_video_lost_schedule_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_video_shelter_schedule_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmScheduleInfo:
    """Fetch read-only video-shelter alarm schedule via `/tdkcgi`."""

    return request_alarm_video_shelter_schedule_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_alarm_input_schedule_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceAlarmScheduleInfo:
    """Fetch read-only alarm-input schedule via `/tdkcgi`."""

    return request_alarm_input_schedule_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_human_trace_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceHumanTraceInfo:
    """Fetch read-only human-trace state via `/tdkcgi`."""

    return request_human_trace_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_move_detection_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceMoveDetectionInfo:
    """Fetch read-only move-detection state via `/tdkcgi`."""

    return request_move_detection_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_fps_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = -1,
    stream_id: int = -1,
) -> DeviceFpsInfo:
    """Fetch read-only FPS settings via `/tdkcgi`."""

    return request_fps_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        stream_id=stream_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_ptz_state_info(endpoint: DeviceCgiEndpoint) -> DevicePtzStateInfo:
    """Fetch read-only PTZ position state via `/tdkcgi`."""

    return request_ptz_state_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_ptz_preset_info(endpoint: DeviceCgiEndpoint) -> DevicePtzPresetInfo:
    """Fetch read-only PTZ preset list via `/tdkcgi`."""

    return request_ptz_preset_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_upgrade_version_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceUpgradeVersionInfo:
    """Fetch read-only latest firmware version via `/tdkcgi`."""

    return request_upgrade_version_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_upgrade_status_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceUpgradeStatusInfo:
    """Fetch read-only firmware upgrade status via `/tdkcgi`."""

    return request_upgrade_status_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_upgrade_process_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceUpgradeProcessInfo:
    """Fetch read-only firmware upgrade progress via `/tdkcgi`."""

    return request_upgrade_process_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_smart_light_info(
    endpoint: DeviceCgiEndpoint,
    *,
    room: int = 1,
) -> DeviceSmartLightInfo:
    """Fetch read-only smart-light state via `/tdkcgi`."""

    return request_smart_light_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        room=room,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_sound_light_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceSoundLightInfo:
    """Fetch read-only sound-and-light one-key state via `/tdkcgi`."""

    return request_sound_light_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_storage_info(endpoint: DeviceCgiEndpoint) -> DeviceStorageInfo:
    """Fetch read-only storage status via `/tdkcgi`."""

    return request_storage_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_tf_card_info(endpoint: DeviceCgiEndpoint) -> DeviceTfCardInfo:
    """Fetch read-only TF-card status via `/tdkcgi`."""

    return request_tf_card_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_product_info(endpoint: DeviceCgiEndpoint) -> DeviceProductInfo:
    """Fetch read-only product identity via `/tdkcgi`."""

    return request_product_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_time_info(endpoint: DeviceCgiEndpoint) -> DeviceTimeInfo:
    """Fetch read-only device time/timezone via `/tdkcgi`."""

    return request_time_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_stream_key_info(endpoint: DeviceCgiEndpoint) -> DeviceStreamKeyInfo:
    """Fetch read-only stream key metadata via `/tdkcgi`."""

    return request_stream_key_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_qr_code_info(endpoint: DeviceCgiEndpoint) -> DeviceQrCodeInfo:
    """Fetch read-only device QR code via `/tdkcgi`."""

    return request_qr_code_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_record_config_info(
    endpoint: DeviceCgiEndpoint,
    *,
    channel_id: int = 1,
) -> DeviceRecordConfigInfo:
    """Fetch read-only record configuration via `/tdkcgi`."""

    return request_record_config_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        channel_id=channel_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_record_session_info(
    endpoint: DeviceCgiEndpoint,
    *,
    start_time: str,
    end_time: str,
    channel_id: int = 1,
    file_type: str = "all",
    occur_type: str = "all",
    stream: str = "all",
) -> DeviceRecordSessionInfo:
    """Fetch read-only record search session via `/tdkcgi`."""

    return request_record_session_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        start_time=start_time,
        end_time=end_time,
        channel_id=channel_id,
        file_type=file_type,
        occur_type=occur_type,
        stream=stream,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_record_message_info(
    endpoint: DeviceCgiEndpoint,
    *,
    session_id: str,
) -> DeviceRecordMessageInfo:
    """Fetch one read-only record-message page via `/tdkcgi`."""

    return request_record_message_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        session_id=session_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_record_alarm_info(
    endpoint: DeviceCgiEndpoint,
    *,
    timestamp: str,
    channel_id: int = 1,
    file_type: str = "all",
    occur_type: str = "all",
    stream: str = "all",
    alarm_type: int | None = None,
    alarm_id: str | None = None,
) -> DeviceRecordAlarmInfo:
    """Fetch read-only alarm-linked archive records via `/tdkcgi`."""

    return request_record_alarm_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        timestamp=timestamp,
        channel_id=channel_id,
        file_type=file_type,
        occur_type=occur_type,
        stream=stream,
        alarm_type=alarm_type,
        alarm_id=alarm_id,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_record_list_info(
    endpoint: DeviceCgiEndpoint,
    *,
    start_time: str,
    end_time: str,
    channel_id: int = 1,
    file_type: str = "all",
    occur_type: str = "all",
    stream: str = "all",
    max_pages: int = 32,
) -> DeviceRecordListInfo:
    """Fetch archive records via the native session/message CGI sequence."""

    if max_pages < 1:
        raise ValueError("max_pages must be greater than 0")

    session = fetch_record_session_info(
        endpoint,
        start_time=start_time,
        end_time=end_time,
        channel_id=channel_id,
        file_type=file_type,
        occur_type=occur_type,
        stream=stream,
    )
    if session.error != 0 or not session.session_id:
        return DeviceRecordListInfo(
            error=session.error,
            session_id=session.session_id,
            session=session,
        )

    records: list[DeviceRecordFileInfo] = []
    pages: list[DeviceRecordMessageInfo] = []
    completed = False
    error = session.error
    for _page_number in range(max_pages):
        page = fetch_record_message_info(
            endpoint, session_id=session.session_id
        )
        pages.append(page)
        records.extend(page.records)
        error = page.error
        if page.error != 0:
            break
        if page.result == 0:
            completed = True
            break
        if page.result is None:
            break

    return DeviceRecordListInfo(
        error=error,
        session_id=session.session_id,
        records=records,
        pages=pages,
        completed=completed,
        session=session,
    )


def fetch_wifi_list_info(endpoint: DeviceCgiEndpoint) -> DeviceWifiListInfo:
    """Fetch read-only Wi-Fi scan results via `/tdkcgi`."""

    return request_wifi_list_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_screen_flip_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceScreenFlipInfo:
    """Fetch read-only screen flip state via `/tdkcgi`."""

    return request_screen_flip_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_video_switch_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceVideoSwitchInfo:
    """Fetch read-only video switch state via `/tdkcgi`."""

    return request_video_switch_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_time_title_info(endpoint: DeviceCgiEndpoint) -> DeviceTimeTitleInfo:
    """Fetch read-only time-title overlay geometry via `/tdkcgi`."""

    return request_time_title_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_network_info(endpoint: DeviceCgiEndpoint) -> DeviceNetworkInfo:
    """Fetch read-only network settings via `/tdkcgi`."""

    return request_network_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_network_base_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceNetworkBaseInfo:
    """Fetch read-only extended network base settings via `/tdkcgi`."""

    return request_network_base_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_system_general_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceGeneralInfo:
    """Fetch read-only system general settings via `/tdkcgi`."""

    return request_system_general_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_system_capabilities(
    endpoint: DeviceCgiEndpoint,
) -> DeviceCapabilitiesInfo:
    """Fetch read-only system capabilities via `/tdkcgi`."""

    return request_system_capabilities(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_video_config_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceVideoConfigInfo:
    """Fetch read-only video encode configuration via `/tdkcgi`."""

    return request_video_config_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_device_profile(endpoint: DeviceCgiEndpoint) -> CameraDeviceProfile:
    """Fetch an aggregated read-only local CGI profile."""

    all_info = fetch_device_all_info(endpoint)
    product = fetch_product_info(endpoint)
    time = fetch_time_info(endpoint)
    storage = fetch_storage_info(endpoint)
    network = fetch_network_info(endpoint)
    general = fetch_system_general_info(endpoint)
    capabilities = fetch_system_capabilities(endpoint)
    video_config = fetch_video_config_info(endpoint)
    wifi = fetch_wifi_list_info(endpoint)
    screen_flip = fetch_screen_flip_info(endpoint)
    video_switch = fetch_video_switch_info(endpoint)
    time_title = fetch_time_title_info(endpoint)
    return CameraDeviceProfile(
        all_info=all_info,
        product=product,
        time=time,
        storage=storage,
        network=network,
        general=general,
        capabilities=capabilities,
        video_config=video_config,
        wifi=wifi,
        screen_flip=screen_flip,
        video_switch=video_switch,
        time_title=time_title,
        command_statuses=(
            command_status_for_response(COMMAND_GET_DEVICE_ALL_INFO, all_info),
            command_status_for_response(COMMAND_GET_PRODUCT_INFO, product),
            command_status_for_response(COMMAND_GET_TIME_INFO, time),
            command_status_for_response(COMMAND_GET_STORAGE_INFO, storage),
            command_status_for_response(COMMAND_GET_NETWORK_INFO, network),
            command_status_for_response(COMMAND_GET_SYSTEM_GENERAL, general),
            command_status_for_response(
                COMMAND_GET_SYSTEM_ABILITY, capabilities
            ),
            command_status_for_response(
                COMMAND_GET_VIDEO_CONFIG, video_config
            ),
            command_status_for_response(COMMAND_GET_WIFI_LIST, wifi),
            command_status_for_response(COMMAND_GET_SCREEN_FLIP, screen_flip),
            command_status_for_response(
                COMMAND_GET_VIDEO_SWITCH, video_switch
            ),
            command_status_for_response(COMMAND_GET_TIME_TITLE, time_title),
        ),
    )

"""Read-only client helpers for the device `/tdkcgi` endpoint."""

import xml.etree.ElementTree as ET
from typing import Any

from quii_helper.device.cgi.models import (
    DeviceAlarmChannelInfo,
    DeviceAlarmInputInfo,
    DeviceAlarmMotionDetectionInfo,
    DeviceAlarmScheduleInfo,
    DeviceAlarmVideoLostInfo,
    DeviceAlarmVideoShelterInfo,
    DeviceAllInfo,
    DeviceAttachmentInfo,
    DeviceCapabilitiesInfo,
    DeviceCgiResponse,
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
)
from quii_helper.device.cgi.parser import (
    parse_alarm_channel_info,
    parse_alarm_input_info,
    parse_alarm_input_schedule_info,
    parse_alarm_motion_detection_info,
    parse_alarm_motion_detection_schedule_info,
    parse_alarm_video_lost_info,
    parse_alarm_video_lost_schedule_info,
    parse_alarm_video_shelter_info,
    parse_alarm_video_shelter_schedule_info,
    parse_cgi_response,
    parse_device_all_info,
    parse_device_attachment_info,
    parse_fps_info,
    parse_human_trace_info,
    parse_motion_detection_info,
    parse_move_detection_info,
    parse_network_base_info,
    parse_network_info,
    parse_product_info,
    parse_ptz_preset_info,
    parse_ptz_state_info,
    parse_qr_code_info,
    parse_record_alarm_info,
    parse_record_config_info,
    parse_record_message_info,
    parse_record_session_info,
    parse_screen_flip_info,
    parse_smart_light_info,
    parse_sound_light_info,
    parse_storage_info,
    parse_stream_key_info,
    parse_system_capabilities,
    parse_system_general_info,
    parse_tf_card_info,
    parse_time_info,
    parse_time_title_info,
    parse_upgrade_process_info,
    parse_upgrade_status_info,
    parse_upgrade_version_info,
    parse_video_config_info,
    parse_video_switch_info,
    parse_wifi_list_info,
)
from quii_helper.device.http.transport import request_cgi
from quii_helper.device.security.auth import encode_device_password

COMMAND_GET_DEVICE_ALL_INFO = "get.device.status"
COMMAND_GET_ALARM_CHANNEL_INFO = "get.encode.channelname"
COMMAND_GET_ALARM_INPUT = "get.alarm.alarmin"
COMMAND_GET_ALARM_INPUT_SCHEDULE = "get.alarm.alarmin.schedule"
COMMAND_GET_ALARM_MOTION_DETECTION = "get.alarm.motiondetection"
COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE = (
    "get.alarm.motiondetection.schedule"
)
COMMAND_GET_ALARM_VIDEO_LOST = "get.alarm.videolost"
COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE = "get.alarm.videolost.schedule"
COMMAND_GET_ALARM_VIDEO_SHELTER = "get.alarm.videoshelter"
COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE = "get.alarm.videoshelter.schedule"
COMMAND_GET_STORAGE_INFO = "get.hdd.base"
COMMAND_GET_NETWORK_INFO = "get.network.config"
COMMAND_GET_NETWORK_BASE_INFO = "get.network.base"
COMMAND_GET_SYSTEM_GENERAL = "get.system.general"
COMMAND_GET_SYSTEM_ABILITY = "get.system.ability"
COMMAND_GET_VIDEO_CONFIG = "get.encode"
COMMAND_GET_PRODUCT_INFO = "get.product.info"
COMMAND_GET_TIME_INFO = "get.product.time"
COMMAND_GET_STREAM_KEY_INFO = "get.device.streamkey"
COMMAND_GET_QR_CODE_INFO = "get.device.qrcode"
COMMAND_GET_RECORD_ALARM_INFO = "get.record.alarmrecord"
COMMAND_GET_RECORD_CONFIG_INFO = "get.record.config"
COMMAND_GET_RECORD_MESSAGE_INFO = "get.record.message"
COMMAND_GET_RECORD_SESSION_INFO = "get.record.session"
COMMAND_GET_WIFI_LIST = "get.wifi.list"
COMMAND_GET_SCREEN_FLIP = "get.shape.mirror"
COMMAND_GET_VIDEO_SWITCH = "get.videoswitch.vionoff"
COMMAND_GET_TIME_TITLE = "get.video.timetitle"
COMMAND_GET_DEVICE_ATTACHMENT_INFO = "get.device.attachInfo"
COMMAND_GET_MOTION_DETECTION_INFO = "get.motiondetection.info"
COMMAND_GET_HUMAN_TRACE_INFO = "get.humantrace.info"
COMMAND_GET_MOVE_DETECTION_INFO = "get.movedetection.info"
COMMAND_GET_FPS_INFO = "get.encode.fps"
COMMAND_GET_SMART_LIGHT_INFO = "get.smart.lightinfo"
COMMAND_GET_SOUND_LIGHT_INFO = "get.soundandlight.state"
COMMAND_GET_TF_CARD_INFO = "get.tfcard.info"
COMMAND_GET_PTZ_STATE_INFO = "get.ptz.position"
COMMAND_GET_PTZ_PRESET_INFO = "get.ptz.preset"
COMMAND_GET_UPGRADE_VERSION_INFO = "get.system.upgradeversion"
COMMAND_GET_UPGRADE_STATUS_INFO = "get.system.upgradestatus"
COMMAND_GET_UPGRADE_PROCESS_INFO = "get.system.upgradeprocess"
DEFAULT_CGI_USERNAME = "adminapp2"
DEFAULT_CGI_HTTP_PORT = 80


def request_readonly_cgi(
    command: str,
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    username: str = DEFAULT_CGI_USERNAME,
    verify_tls: bool = True,
    content: ET.Element | None = None,
    debug: bool = False,
) -> DeviceCgiResponse:
    """Request a read-only CGI command using the original LAN auth header."""

    kwargs: dict[str, Any] = {
        "command": command,
        "host": host,
        "port": port,
        "username": username,
        "password": encode_device_password(auth_code),
        "encrypted": False,
        "scheme": scheme,
        "passwordencode": "1",
        "verify_tls": verify_tls,
        "debug": debug,
    }
    if content is not None:
        kwargs["content"] = content
    result = request_cgi(**kwargs)
    return parse_cgi_response(command, result["raw"])


def request_device_all_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAllInfo:
    """Fetch `get.device.status` from `/tdkcgi`."""

    return parse_device_all_info(
        request_readonly_cgi(
            COMMAND_GET_DEVICE_ALL_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_alarm_channel_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmChannelInfo:
    """Fetch `get.encode.channelname` from `/tdkcgi`."""

    return parse_alarm_channel_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_CHANNEL_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_storage_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceStorageInfo:
    """Fetch `get.hdd.base` from `/tdkcgi`."""

    return parse_storage_info(
        request_readonly_cgi(
            COMMAND_GET_STORAGE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_tf_card_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceTfCardInfo:
    """Fetch `get.tfcard.info` from `/tdkcgi`."""

    return parse_tf_card_info(
        request_readonly_cgi(
            COMMAND_GET_TF_CARD_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_product_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceProductInfo:
    """Fetch `get.product.info` from `/tdkcgi`."""

    return parse_product_info(
        request_readonly_cgi(
            COMMAND_GET_PRODUCT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_time_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceTimeInfo:
    """Fetch `get.product.time` from `/tdkcgi`."""

    return parse_time_info(
        request_readonly_cgi(
            COMMAND_GET_TIME_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_stream_key_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceStreamKeyInfo:
    """Fetch `get.device.streamkey` from `/tdkcgi`."""

    return parse_stream_key_info(
        request_readonly_cgi(
            COMMAND_GET_STREAM_KEY_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_qr_code_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceQrCodeInfo:
    """Fetch `get.device.qrcode` from `/tdkcgi`."""

    return parse_qr_code_info(
        request_readonly_cgi(
            COMMAND_GET_QR_CODE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_record_config_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceRecordConfigInfo:
    """Fetch `get.record.config` from `/tdkcgi`."""

    return parse_record_config_info(
        request_readonly_cgi(
            COMMAND_GET_RECORD_CONFIG_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_record_session_info(
    *,
    host: str,
    auth_code: str,
    start_time: str,
    end_time: str,
    channel_id: int = 1,
    file_type: str = "all",
    occur_type: str = "all",
    stream: str = "all",
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceRecordSessionInfo:
    """Fetch `get.record.session` from `/tdkcgi`."""

    return parse_record_session_info(
        request_readonly_cgi(
            COMMAND_GET_RECORD_SESSION_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_record_search_content(
                channel_id=channel_id,
                start_time=start_time,
                end_time=end_time,
                file_type=file_type,
                occur_type=occur_type,
                stream=stream,
            ),
            debug=debug,
        )
    )


def request_record_message_info(
    *,
    host: str,
    auth_code: str,
    session_id: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceRecordMessageInfo:
    """Fetch `get.record.message` from `/tdkcgi`."""

    return parse_record_message_info(
        request_readonly_cgi(
            COMMAND_GET_RECORD_MESSAGE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_record_id_content(session_id),
            debug=debug,
        )
    )


def request_record_alarm_info(
    *,
    host: str,
    auth_code: str,
    timestamp: str,
    channel_id: int = 1,
    file_type: str = "all",
    occur_type: str = "all",
    stream: str = "all",
    alarm_type: int | None = None,
    alarm_id: str | None = None,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceRecordAlarmInfo:
    """Fetch `get.record.alarmrecord` from `/tdkcgi`."""

    return parse_record_alarm_info(
        request_readonly_cgi(
            COMMAND_GET_RECORD_ALARM_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_record_alarm_content(
                channel_id=channel_id,
                timestamp=timestamp,
                file_type=file_type,
                occur_type=occur_type,
                stream=stream,
                alarm_type=alarm_type,
                alarm_id=alarm_id,
            ),
            debug=debug,
        )
    )


def request_wifi_list_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceWifiListInfo:
    """Fetch `get.wifi.list` from `/tdkcgi`."""

    return parse_wifi_list_info(
        request_readonly_cgi(
            COMMAND_GET_WIFI_LIST,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_screen_flip_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceScreenFlipInfo:
    """Fetch `get.shape.mirror` from `/tdkcgi`."""

    return parse_screen_flip_info(
        request_readonly_cgi(
            COMMAND_GET_SCREEN_FLIP,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_video_switch_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceVideoSwitchInfo:
    """Fetch `get.videoswitch.vionoff` from `/tdkcgi`."""

    return parse_video_switch_info(
        request_readonly_cgi(
            COMMAND_GET_VIDEO_SWITCH,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_time_title_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceTimeTitleInfo:
    """Fetch `get.video.timetitle` from `/tdkcgi`."""

    return parse_time_title_info(
        request_readonly_cgi(
            COMMAND_GET_TIME_TITLE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_network_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceNetworkInfo:
    """Fetch `get.network.config` from `/tdkcgi`."""

    return parse_network_info(
        request_readonly_cgi(
            COMMAND_GET_NETWORK_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_network_base_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceNetworkBaseInfo:
    """Fetch `get.network.base` from `/tdkcgi`."""

    return parse_network_base_info(
        request_readonly_cgi(
            COMMAND_GET_NETWORK_BASE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_device_attachment_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAttachmentInfo:
    """Fetch `get.device.attachInfo` from `/tdkcgi`."""

    return parse_device_attachment_info(
        request_readonly_cgi(
            COMMAND_GET_DEVICE_ATTACHMENT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_motion_detection_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceMotionDetectionInfo:
    """Fetch `get.motiondetection.info` from `/tdkcgi`."""

    return parse_motion_detection_info(
        request_readonly_cgi(
            COMMAND_GET_MOTION_DETECTION_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_alarm_motion_detection_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmMotionDetectionInfo:
    """Fetch `get.alarm.motiondetection` from `/tdkcgi`."""

    return parse_alarm_motion_detection_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_MOTION_DETECTION,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_video_lost_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmVideoLostInfo:
    """Fetch `get.alarm.videolost` from `/tdkcgi`."""

    return parse_alarm_video_lost_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_VIDEO_LOST,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_video_shelter_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmVideoShelterInfo:
    """Fetch `get.alarm.videoshelter` from `/tdkcgi`."""

    return parse_alarm_video_shelter_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_VIDEO_SHELTER,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_input_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = -1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmInputInfo:
    """Fetch `get.alarm.alarmin` from `/tdkcgi`."""

    return parse_alarm_input_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_INPUT,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=(
                None
                if channel_id == -1
                else _single_value_content("channel", channel_id)
            ),
            debug=debug,
        )
    )


def request_alarm_motion_detection_schedule_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmScheduleInfo:
    """Fetch `get.alarm.motiondetection.schedule` from `/tdkcgi`."""

    return parse_alarm_motion_detection_schedule_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_video_lost_schedule_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmScheduleInfo:
    """Fetch `get.alarm.videolost.schedule` from `/tdkcgi`."""

    return parse_alarm_video_lost_schedule_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_video_shelter_schedule_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmScheduleInfo:
    """Fetch `get.alarm.videoshelter.schedule` from `/tdkcgi`."""

    return parse_alarm_video_shelter_schedule_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_alarm_input_schedule_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAlarmScheduleInfo:
    """Fetch `get.alarm.alarmin.schedule` from `/tdkcgi`."""

    return parse_alarm_input_schedule_info(
        request_readonly_cgi(
            COMMAND_GET_ALARM_INPUT_SCHEDULE,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_human_trace_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceHumanTraceInfo:
    """Fetch `get.humantrace.info` from `/tdkcgi`."""

    return parse_human_trace_info(
        request_readonly_cgi(
            COMMAND_GET_HUMAN_TRACE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_move_detection_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceMoveDetectionInfo:
    """Fetch `get.movedetection.info` from `/tdkcgi`."""

    return parse_move_detection_info(
        request_readonly_cgi(
            COMMAND_GET_MOVE_DETECTION_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_ptz_state_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DevicePtzStateInfo:
    """Fetch `get.ptz.position` from `/tdkcgi`."""

    return parse_ptz_state_info(
        request_readonly_cgi(
            COMMAND_GET_PTZ_STATE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_ptz_preset_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DevicePtzPresetInfo:
    """Fetch `get.ptz.preset` from `/tdkcgi`."""

    return parse_ptz_preset_info(
        request_readonly_cgi(
            COMMAND_GET_PTZ_PRESET_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_upgrade_version_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceUpgradeVersionInfo:
    """Fetch `get.system.upgradeversion` from `/tdkcgi`."""

    return parse_upgrade_version_info(
        request_readonly_cgi(
            COMMAND_GET_UPGRADE_VERSION_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_upgrade_status_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceUpgradeStatusInfo:
    """Fetch `get.system.upgradestatus` from `/tdkcgi`."""

    return parse_upgrade_status_info(
        request_readonly_cgi(
            COMMAND_GET_UPGRADE_STATUS_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_upgrade_process_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceUpgradeProcessInfo:
    """Fetch `get.system.upgradeprocess` from `/tdkcgi`."""

    return parse_upgrade_process_info(
        request_readonly_cgi(
            COMMAND_GET_UPGRADE_PROCESS_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_fps_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = -1,
    stream_id: int = -1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceFpsInfo:
    """Fetch `get.encode.fps` from `/tdkcgi`."""

    return parse_fps_info(
        request_readonly_cgi(
            COMMAND_GET_FPS_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_channel_stream_content(channel_id, stream_id),
            debug=debug,
        ),
        channel_id=channel_id,
        stream_id=stream_id,
    )


def request_smart_light_info(
    *,
    host: str,
    auth_code: str,
    room: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceSmartLightInfo:
    """Fetch `get.smart.lightinfo` from `/tdkcgi`."""

    return parse_smart_light_info(
        request_readonly_cgi(
            COMMAND_GET_SMART_LIGHT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("room", room),
            debug=debug,
        )
    )


def request_sound_light_info(
    *,
    host: str,
    auth_code: str,
    channel_id: int = 1,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceSoundLightInfo:
    """Fetch `get.soundandlight.state` from `/tdkcgi`."""

    return parse_sound_light_info(
        request_readonly_cgi(
            COMMAND_GET_SOUND_LIGHT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            content=_single_value_content("channel", channel_id),
            debug=debug,
        )
    )


def request_system_general_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceGeneralInfo:
    """Fetch `get.system.general` from `/tdkcgi`."""

    return parse_system_general_info(
        request_readonly_cgi(
            COMMAND_GET_SYSTEM_GENERAL,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def _channel_stream_content(channel_id: int, stream_id: int) -> ET.Element:
    channel = ET.Element("channel")
    ET.SubElement(channel, "id").text = str(channel_id)
    ET.SubElement(channel, "stream").text = str(stream_id)
    return channel


def _single_value_content(name: str, value: object) -> ET.Element:
    element = ET.Element(name)
    element.text = str(value)
    return element


def _record_search_content(
    *,
    channel_id: int,
    start_time: str,
    end_time: str,
    file_type: str,
    occur_type: str,
    stream: str,
) -> ET.Element:
    record = ET.Element("record")
    ET.SubElement(record, "filetype").text = file_type
    ET.SubElement(record, "occurtype").text = occur_type
    ET.SubElement(record, "channel").text = str(channel_id)
    ET.SubElement(record, "starttime").text = start_time
    ET.SubElement(record, "endtime").text = end_time
    ET.SubElement(record, "stream").text = stream
    return record


def _record_id_content(session_id: str) -> ET.Element:
    record = ET.Element("record")
    ET.SubElement(record, "id").text = session_id
    return record


def _record_alarm_content(
    *,
    channel_id: int,
    timestamp: str,
    file_type: str,
    occur_type: str,
    stream: str,
    alarm_type: int | None,
    alarm_id: str | None,
) -> ET.Element:
    record = ET.Element("record")
    ET.SubElement(record, "filetype").text = file_type
    ET.SubElement(record, "stream").text = stream
    ET.SubElement(record, "occurtype").text = occur_type
    ET.SubElement(record, "channel").text = str(channel_id)
    ET.SubElement(record, "timestamp").text = timestamp
    if alarm_type is not None:
        ET.SubElement(record, "alarmtype").text = str(alarm_type)
    if alarm_id:
        ET.SubElement(record, "alarmid").text = alarm_id
    return record


def request_system_capabilities(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceCapabilitiesInfo:
    """Fetch `get.system.ability` from `/tdkcgi`."""

    return parse_system_capabilities(
        request_readonly_cgi(
            COMMAND_GET_SYSTEM_ABILITY,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_video_config_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceVideoConfigInfo:
    """Fetch `get.encode` from `/tdkcgi`."""

    return parse_video_config_info(
        request_readonly_cgi(
            COMMAND_GET_VIDEO_CONFIG,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )

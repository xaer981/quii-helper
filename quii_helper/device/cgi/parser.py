"""XML parsing helpers for read-only `/tdkcgi` responses."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from quii_helper.device.cgi.models import (
    DeviceAlarmChannel,
    DeviceAlarmChannelInfo,
    DeviceAlarmInputChannel,
    DeviceAlarmInputInfo,
    DeviceAlarmMotionDetectionInfo,
    DeviceAlarmScheduleDay,
    DeviceAlarmScheduleInfo,
    DeviceAlarmScheduleSlot,
    DeviceAlarmVideoLostInfo,
    DeviceAlarmVideoShelterInfo,
    DeviceAllInfo,
    DeviceAttachmentAlarm,
    DeviceAttachmentChannel,
    DeviceAttachmentElevator,
    DeviceAttachmentInfo,
    DeviceAttachmentLock,
    DeviceAttachmentProfile,
    DeviceAttachmentSmartSwitch,
    DeviceCapabilitiesInfo,
    DeviceCgiResponse,
    DeviceFpsChannelInfo,
    DeviceFpsInfo,
    DeviceGeneralInfo,
    DeviceHumanTraceInfo,
    DeviceLanInfo,
    DeviceMotionDetectionInfo,
    DeviceMoveDetectionInfo,
    DeviceNetworkBaseAbility,
    DeviceNetworkBaseInfo,
    DeviceNetworkInfo,
    DeviceNetworkTransferPolicy,
    DeviceProductInfo,
    DevicePtzPreset,
    DevicePtzPresetInfo,
    DevicePtzStateInfo,
    DeviceQrCodeInfo,
    DeviceRecordAlarmInfo,
    DeviceRecordConfigInfo,
    DeviceRecordFileInfo,
    DeviceRecordMessageInfo,
    DeviceRecordScheduleTime,
    DeviceRecordSessionInfo,
    DeviceScreenFlipInfo,
    DeviceSmartLightInfo,
    DeviceSmartLightItem,
    DeviceSoundLightChannelInfo,
    DeviceSoundLightInfo,
    DeviceStorageDisk,
    DeviceStorageInfo,
    DeviceStreamKeyInfo,
    DeviceTfCardDiskInfo,
    DeviceTfCardInfo,
    DeviceTimeInfo,
    DeviceTimeTitleInfo,
    DeviceTimeTitleOverlay,
    DeviceUpgradeProcessInfo,
    DeviceUpgradeStatusInfo,
    DeviceUpgradeVersionInfo,
    DeviceVideoChannelInfo,
    DeviceVideoConfigInfo,
    DeviceVideoStreamInfo,
    DeviceVideoSwitchInfo,
    DeviceWifiListInfo,
    DeviceWifiNetwork,
)

_RECORD_SCHEDULE_DAYS = (
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
)

_ALARM_SCHEDULE_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def parse_cgi_response(command: str, raw_xml: str) -> DeviceCgiResponse:
    """Parse a device CGI XML response into a generic response model."""

    root = ET.fromstring(raw_xml.encode("utf-8"))
    body = root.find("./body")
    if body is None:
        raise ValueError("CGI response body not found")

    error = _to_int(body.findtext("error"), default=0) or 0
    content = body.find("content")
    return DeviceCgiResponse(
        command=command,
        error=error,
        content=_children_to_dict(content) if content is not None else {},
        raw_xml=raw_xml,
    )


def parse_storage_info(response: DeviceCgiResponse) -> DeviceStorageInfo:
    """Map `get.hdd.base` content into `DeviceStorageInfo`."""

    base = _as_dict(_lookup(response.content, "hdd", "base"))
    disks = [
        DeviceStorageDisk(
            exists=_to_bool(_as_dict(item).get("exist")) or False,
            disk_id=_to_str(_as_dict(item).get("diskid")),
            status=_to_str(_as_dict(item).get("status")),
            name=_to_str(_as_dict(item).get("name")),
            attributes=_to_str(_as_dict(item).get("attr")),
            type=_to_str(_as_dict(item).get("type")),
            total=_to_int(_as_dict(item).get("total")),
            free=_to_int(_as_dict(item).get("free")),
            group_id=_to_str(_as_dict(item).get("groupid")),
        )
        for item in _data_items(base.get("datalist"))
    ]
    return DeviceStorageInfo(
        error=response.error,
        total_sum=_to_int(base.get("totalsum")),
        free_sum=_to_int(base.get("freesum")),
        mode=_to_str(base.get("mode")),
        group_max=_to_str(base.get("groupmax")),
        disks=disks,
        raw=response,
    )


def parse_tf_card_info(response: DeviceCgiResponse) -> DeviceTfCardInfo:
    """Map `get.tfcard.info` content into `DeviceTfCardInfo`."""

    formatting = _to_bool(response.content.get("formatting"))
    disks: list[DeviceTfCardDiskInfo] = []
    if formatting is not True:
        disks = [
            _parse_tf_card_disk(_as_dict(item))
            for item in _data_items(response.content.get("datalist"))
        ]
    return DeviceTfCardInfo(
        error=response.error,
        formatting=formatting,
        total_sum=_to_int(response.content.get("totalsum")),
        free_sum=_to_int(response.content.get("freesum")),
        disks=disks,
        content=response.content,
        raw=response,
    )


def parse_product_info(response: DeviceCgiResponse) -> DeviceProductInfo:
    """Map `get.product.info` content into `DeviceProductInfo`."""

    info = _as_dict(response.content.get("info"))
    return DeviceProductInfo(
        error=response.error,
        mac=_to_str(info.get("mac")),
        version=_to_str(info.get("version")),
        release_date=_to_str(info.get("releasedate")),
        model=_to_str(info.get("model")),
        raw=response,
    )


def parse_time_info(response: DeviceCgiResponse) -> DeviceTimeInfo:
    """Map `get.product.time` content into `DeviceTimeInfo`."""

    time_info = _as_dict(response.content.get("time"))
    return DeviceTimeInfo(
        error=response.error,
        time_zone=_to_str(time_info.get("timezone")),
        date_time=_to_str(time_info.get("datetime")),
        raw=response,
    )


def parse_stream_key_info(response: DeviceCgiResponse) -> DeviceStreamKeyInfo:
    """Map `get.device.streamkey` content into `DeviceStreamKeyInfo`."""

    return DeviceStreamKeyInfo(
        error=response.error,
        key=_to_str(response.content.get("key")),
        tdc=_to_str(response.content.get("tdc")),
        sync_time=_to_str(response.content.get("synctime")),
        raw=response,
    )


def parse_qr_code_info(response: DeviceCgiResponse) -> DeviceQrCodeInfo:
    """Map `get.device.qrcode` content into `DeviceQrCodeInfo`."""

    return DeviceQrCodeInfo(
        error=response.error,
        qr_code=_to_str(response.content.get("qrcode")),
        raw=response,
    )


def parse_record_config_info(
    response: DeviceCgiResponse,
) -> DeviceRecordConfigInfo:
    """Map `get.record.config` content into `DeviceRecordConfigInfo`."""

    channel = _as_dict(response.content.get("channel"))
    record_config = _as_dict(channel.get("recordconfig"))
    schedule = _as_dict(record_config.get("schedule"))
    return DeviceRecordConfigInfo(
        error=response.error,
        channel_id=_to_int(channel.get("id")),
        record_stream=_to_str(record_config.get("recordstream")),
        prerecord=_to_int(record_config.get("prerecord")),
        redundancy=_to_bool(record_config.get("redundancy")),
        packet_length=_to_int(record_config.get("packetlength")),
        record_control=_to_str(record_config.get("recordcontrol")),
        schedule={
            day: _parse_record_schedule_day(_as_dict(schedule.get(day)))
            for day in _RECORD_SCHEDULE_DAYS
        },
        raw=response,
    )


def parse_record_session_info(
    response: DeviceCgiResponse,
) -> DeviceRecordSessionInfo:
    """Map `get.record.session` content into `DeviceRecordSessionInfo`."""

    record = _as_dict(response.content.get("record"))
    return DeviceRecordSessionInfo(
        error=response.error,
        session_id=_to_str(record.get("id")),
        raw=response,
    )


def parse_record_message_info(
    response: DeviceCgiResponse,
) -> DeviceRecordMessageInfo:
    """Map `get.record.message` content into `DeviceRecordMessageInfo`."""

    return DeviceRecordMessageInfo(
        error=response.error,
        records=[
            _parse_record_file(_as_dict(item))
            for item in _record_message_items(response.content)
        ],
        result=_to_int(
            response.content.get("result")
            or response.content.get("status")
            or response.content.get("ret")
        ),
        raw=response,
    )


def parse_record_alarm_info(
    response: DeviceCgiResponse,
) -> DeviceRecordAlarmInfo:
    """Map `get.record.alarmrecord` content into `DeviceRecordAlarmInfo`."""

    return DeviceRecordAlarmInfo(
        error=response.error,
        records=[
            _parse_record_file(_as_dict(item))
            for item in _record_message_items(response.content)
        ],
        result=_to_int(
            response.content.get("result")
            or response.content.get("status")
            or response.content.get("ret")
        ),
        raw=response,
    )


def parse_alarm_channel_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmChannelInfo:
    """Map `get.encode.channelname` content into `DeviceAlarmChannelInfo`."""

    return DeviceAlarmChannelInfo(
        error=response.error,
        channels=[
            _parse_alarm_channel(_as_dict(item))
            for item in _alarm_channel_items(response.content)
        ],
        raw=response,
    )


def parse_wifi_list_info(response: DeviceCgiResponse) -> DeviceWifiListInfo:
    """Map `get.wifi.list` content into `DeviceWifiListInfo`."""

    networks = []
    for item in _data_items(response.content.get("wifilist")):
        wifi = _as_dict(item)
        ssid = _to_str(wifi.get("ssid"))
        if not ssid:
            continue
        encrypt = _to_str(wifi.get("encry"))
        networks.append(
            DeviceWifiNetwork(
                network_id=_to_str(wifi.get("id")),
                ssid=ssid,
                rssi=_to_int(wifi.get("rssi")),
                is_encrypted=encrypt.lower() != "1",
            )
        )
    return DeviceWifiListInfo(
        error=response.error,
        networks=networks,
        raw=response,
    )


def parse_screen_flip_info(
    response: DeviceCgiResponse,
) -> DeviceScreenFlipInfo:
    """Map `get.shape.mirror` content into `DeviceScreenFlipInfo`."""

    mirror = _to_str(_value_of(response.content.get("mirror")))
    rotate = _to_str(_value_of(response.content.get("rotate")))
    return DeviceScreenFlipInfo(
        error=response.error,
        mirror=mirror,
        rotate=rotate,
        state=1 if mirror == "up_down" else 0,
        angle=_rotation_angle(rotate),
        raw=response,
    )


def parse_video_switch_info(
    response: DeviceCgiResponse,
) -> DeviceVideoSwitchInfo:
    """Map `get.videoswitch.vionoff` content into `DeviceVideoSwitchInfo`."""

    value = _to_str(_value_of(response.content.get("vionoff")))
    is_on = value == "video_on"
    return DeviceVideoSwitchInfo(
        error=response.error,
        value=value,
        state=1 if is_on else 0,
        is_on=is_on,
        raw=response,
    )


def parse_time_title_info(response: DeviceCgiResponse) -> DeviceTimeTitleInfo:
    """Map `get.video.timetitle` content into `DeviceTimeTitleInfo`."""

    overlays = [
        _parse_time_title_overlay(_as_dict(item))
        for item in _data_items(response.content.get("datalist"))
    ]
    return DeviceTimeTitleInfo(
        error=response.error,
        overlays=overlays,
        raw=response,
    )


def parse_device_attachment_info(
    response: DeviceCgiResponse,
) -> DeviceAttachmentInfo:
    """Map `get.device.attachInfo` content into `DeviceAttachmentInfo`."""

    channel_info = _as_dict(response.content.get("channelinfo"))
    elevator_info = _as_dict(response.content.get("elevatorinfo"))
    alarm = _as_dict(response.content.get("alarm"))
    smart_switch = _as_dict(response.content.get("light"))
    profile = None
    if channel_info:
        profile = DeviceAttachmentProfile(
            total_channel_num=_to_int(channel_info.get("totalnum")),
            cam_num=_to_int(channel_info.get("camnum")),
            cctv_num=_to_int(channel_info.get("cctvnum")),
            ipg_num=_to_int(channel_info.get("ipgnum")),
            manage_num=_to_int(channel_info.get("managenum")),
            ep_num=_to_int(channel_info.get("epnum")),
            switch_direct=_to_bool(
                _lookup(channel_info, "ability", "switchdirectly")
            ),
        )
    return DeviceAttachmentInfo(
        error=response.error,
        profile=profile,
        channels=[
            _parse_attachment_channel(_as_dict(item))
            for item in _named_items(
                channel_info.get("channelList"), "channel"
            )
        ],
        elevators=[
            DeviceAttachmentElevator(
                elevator_id=_to_int(_as_dict(item).get("number")),
                enabled=_to_bool(_as_dict(item).get("enable")),
            )
            for item in _named_items(
                elevator_info.get("elevatorlist"), "elevator"
            )
        ],
        alarms=(
            [
                DeviceAttachmentAlarm(
                    enabled=_to_bool(alarm.get("enable")),
                    mode=_to_int(alarm.get("mode")),
                    numbers=_to_int(alarm.get("numbers")),
                    arming_type=3,
                )
            ]
            if alarm
            else []
        ),
        smart_switches=(
            [
                DeviceAttachmentSmartSwitch(
                    enabled=_to_bool(smart_switch.get("enable")),
                    room=_to_int(smart_switch.get("room")),
                    total=_to_int(smart_switch.get("switch")),
                )
            ]
            if smart_switch
            else []
        ),
        content=response.content,
        raw=response,
    )


def parse_motion_detection_info(
    response: DeviceCgiResponse,
) -> DeviceMotionDetectionInfo:
    """Map `get.motiondetection.info` content into motion settings."""

    channel = _as_dict(response.content.get("channel"))
    motion_detection = _as_dict(channel.get("motiondetection"))
    return DeviceMotionDetectionInfo(
        error=response.error,
        channel_id=_to_int(channel.get("id")),
        enabled=_to_bool(motion_detection.get("enabled")),
        sensitivity=_to_int(motion_detection.get("sensitivity")),
        range=_to_str(motion_detection.get("range")),
        content=response.content,
        raw=response,
    )


def parse_alarm_motion_detection_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmMotionDetectionInfo:
    """Map `get.alarm.motiondetection` content into alarm motion settings."""

    channel = _as_dict(response.content.get("channel"))
    motion_detection = _as_dict(channel.get("motiondetection"))
    region = _as_dict(motion_detection.get("region"))
    return DeviceAlarmMotionDetectionInfo(
        error=response.error,
        channel_id=_to_int(channel.get("id")),
        enabled=_to_bool(motion_detection.get("enabled")),
        sensitivity=_to_int(motion_detection.get("sensitivity")),
        peds_enabled=_to_int(motion_detection.get("pedsenable")),
        row_num=_to_int(region.get("rownum")),
        col_num=_to_int(region.get("colnum")),
        region_data=[
            _to_str(item)
            for item in _named_items(region.get("datalist"), "data")
        ],
        content=response.content,
        raw=response,
    )


def parse_alarm_video_lost_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmVideoLostInfo:
    """Map `get.alarm.videolost` content into video-lost alarm state."""

    channel = _as_dict(response.content.get("channel"))
    video_lost = _as_dict(channel.get("videolost"))
    return DeviceAlarmVideoLostInfo(
        error=response.error,
        channel_id=_to_int(channel.get("id")),
        enabled=_to_bool(video_lost.get("enabled")),
        content=response.content,
        raw=response,
    )


def parse_alarm_video_shelter_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmVideoShelterInfo:
    """Map `get.alarm.videoshelter` content into video-shelter alarm state."""

    channel = _as_dict(response.content.get("channel"))
    video_shelter = _as_dict(channel.get("videoshelter"))
    return DeviceAlarmVideoShelterInfo(
        error=response.error,
        channel_id=_to_int(channel.get("id")),
        enabled=_to_bool(video_shelter.get("enabled")),
        sensitivity=_to_int(video_shelter.get("sensitivity")),
        content=response.content,
        raw=response,
    )


def parse_alarm_input_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmInputInfo:
    """Map `get.alarm.alarmin` content into alarm input channels."""

    return DeviceAlarmInputInfo(
        error=response.error,
        channels=[
            _parse_alarm_input_channel(_as_dict(item))
            for item in _named_items(response.content, "channel")
        ],
        content=response.content,
        raw=response,
    )


def parse_alarm_motion_detection_schedule_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmScheduleInfo:
    """Map `get.alarm.motiondetection.schedule` into alarm schedule slots."""

    return _parse_alarm_schedule_info(response, "motiondetection")


def parse_alarm_video_lost_schedule_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmScheduleInfo:
    """Map `get.alarm.videolost.schedule` into alarm schedule slots."""

    return _parse_alarm_schedule_info(response, "videolost")


def parse_alarm_video_shelter_schedule_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmScheduleInfo:
    """Map `get.alarm.videoshelter.schedule` into alarm schedule slots."""

    return _parse_alarm_schedule_info(response, "videoshelter")


def parse_alarm_input_schedule_info(
    response: DeviceCgiResponse,
) -> DeviceAlarmScheduleInfo:
    """Map `get.alarm.alarmin.schedule` into alarm schedule slots."""

    return _parse_alarm_schedule_info(response, "alarmin")


def parse_human_trace_info(
    response: DeviceCgiResponse,
) -> DeviceHumanTraceInfo:
    """Map `get.humantrace.info` content into enabled state."""

    return DeviceHumanTraceInfo(
        error=response.error,
        enabled=_to_bool(response.content.get("enabled")),
        content=response.content,
        raw=response,
    )


def parse_move_detection_info(
    response: DeviceCgiResponse,
) -> DeviceMoveDetectionInfo:
    """Map `get.movedetection.info` content into enabled state."""

    return DeviceMoveDetectionInfo(
        error=response.error,
        enabled=_to_bool(response.content.get("enabled")),
        content=response.content,
        raw=response,
    )


def parse_ptz_state_info(response: DeviceCgiResponse) -> DevicePtzStateInfo:
    """Map `get.ptz.position` content into PTZ position state."""

    position = _as_dict(response.content.get("position"))
    pos_x = _as_dict(position.get("pos_x"))
    pos_y = _as_dict(position.get("pos_y") or position.get("pox_y"))
    min_x, max_x = _range_bounds(_to_str(pos_x.get("range")))
    min_y, max_y = _range_bounds(_to_str(pos_y.get("range")))
    return DevicePtzStateInfo(
        error=response.error,
        position_x=_to_int(pos_x.get("value")),
        position_y=_to_int(pos_y.get("value")),
        min_x=min_x,
        max_x=max_x,
        min_y=min_y,
        max_y=max_y,
        content=response.content,
        raw=response,
    )


def parse_ptz_preset_info(
    response: DeviceCgiResponse,
) -> DevicePtzPresetInfo:
    """Map `get.ptz.preset` content into PTZ preset entries."""

    return DevicePtzPresetInfo(
        error=response.error,
        presets=[
            DevicePtzPreset(
                preset_id=_to_str(_as_dict(item).get("presetid")),
                name=_to_str(_as_dict(item).get("presetname")),
            )
            for item in _named_items(
                _as_dict(response.content.get("presetlist")), "preset"
            )
        ],
        content=response.content,
        raw=response,
    )


def parse_upgrade_version_info(
    response: DeviceCgiResponse,
) -> DeviceUpgradeVersionInfo:
    """Map `get.system.upgradeversion` content into latest version info."""

    return DeviceUpgradeVersionInfo(
        error=response.error,
        version=_to_str(response.content.get("version")),
        release_time=(
            _to_str(response.content.get("releasetime"))
            or _to_str(response.content.get("time"))
        ),
        content=response.content,
        raw=response,
    )


def parse_upgrade_status_info(
    response: DeviceCgiResponse,
) -> DeviceUpgradeStatusInfo:
    """Map `get.system.upgradestatus` content into upgrade status info."""

    return DeviceUpgradeStatusInfo(
        error=response.error,
        status=_to_int(response.content.get("upgradestatus")),
        version=_to_str(response.content.get("version")),
        time=_to_str(response.content.get("time")),
        content=response.content,
        raw=response,
    )


def parse_upgrade_process_info(
    response: DeviceCgiResponse,
) -> DeviceUpgradeProcessInfo:
    """Map `get.system.upgradeprocess` content into upgrade progress info."""

    return DeviceUpgradeProcessInfo(
        error=response.error,
        process=_to_int(response.content.get("process")),
        content=response.content,
        raw=response,
    )


def parse_fps_info(
    response: DeviceCgiResponse,
    *,
    channel_id: int = -1,
    stream_id: int = -1,
) -> DeviceFpsInfo:
    """Map `get.encode.fps` content into FPS channel entries."""

    response_channels = [
        _as_dict(item) for item in _named_items(response.content, "channel")
    ]
    entries: list[DeviceFpsChannelInfo] = []
    for response_channel_index, response_channel in enumerate(
        _select_response_channels(response_channels, channel_id)
    ):
        fps_values = _fps_values(response_channel.get("fps"))
        for response_stream_index, fps in enumerate(
            _select_response_fps_values(fps_values, stream_id)
        ):
            entries.append(
                DeviceFpsChannelInfo(
                    channel_id=(
                        response_channel_index
                        if channel_id == -1
                        else channel_id
                    ),
                    stream_id=(
                        response_stream_index if stream_id == -1 else stream_id
                    ),
                    fps=fps,
                )
            )
    return DeviceFpsInfo(
        error=response.error,
        channels=entries,
        content=response.content,
        raw=response,
    )


def parse_smart_light_info(
    response: DeviceCgiResponse,
) -> DeviceSmartLightInfo:
    """Map `get.smart.lightinfo` content into smart-light state."""

    return DeviceSmartLightInfo(
        error=response.error,
        room=_to_int(response.content.get("room")),
        light_num=_to_int(response.content.get("lightnum")),
        lights=[
            DeviceSmartLightItem(
                light_no=_to_int(_as_dict(item).get("lightno")),
                name=_to_str(_as_dict(item).get("name")),
                state=_to_int(_as_dict(item).get("state")),
            )
            for item in _named_items(response.content, "lightinfo")
        ],
        content=response.content,
        raw=response,
    )


def parse_sound_light_info(
    response: DeviceCgiResponse,
) -> DeviceSoundLightInfo:
    """Map `get.soundandlight.state` content into one-key control state."""

    return DeviceSoundLightInfo(
        error=response.error,
        channels=[
            DeviceSoundLightChannelInfo(
                channel_id=_to_str(channel.get("id")),
                ctrl_state=_to_int(
                    _as_dict(channel.get("SoundAndLightOneKeyCtrl")).get(
                        "CtrlState"
                    )
                ),
            )
            for item in _named_items(response.content, "channel")
            if (channel := _as_dict(item))
        ],
        content=response.content,
        raw=response,
    )


def parse_network_info(response: DeviceCgiResponse) -> DeviceNetworkInfo:
    """Map `get.network.config` content into `DeviceNetworkInfo`."""

    network = _as_dict(_lookup(response.content, "network"))
    lan_interfaces = [
        _parse_lan_info(_as_dict(item).get("lan", item))
        for item in _data_items(_lookup(network, "base", "lanlist"))
    ]
    return DeviceNetworkInfo(
        error=response.error,
        address=_to_str(network.get("address")),
        subnet_mask=_to_str(network.get("submask")),
        gateway=_to_str(network.get("gateway")),
        dhcp=_to_bool(network.get("idhcp")),
        lan_interfaces=lan_interfaces,
        raw=response,
    )


def parse_network_base_info(
    response: DeviceCgiResponse,
) -> DeviceNetworkBaseInfo:
    """Map `get.network.base` content into `DeviceNetworkBaseInfo`."""

    base = _as_dict(_lookup(response.content, "network", "base"))
    ability = _as_dict(base.get("ability"))
    transfer_policy = _as_dict(base.get("transferpolicy"))
    return DeviceNetworkBaseInfo(
        error=response.error,
        dns=_to_str(base.get("dns")),
        secondary_dns=_to_str(base.get("secondarydns")),
        http_port=_to_int(base.get("httpport")),
        media_port=_to_int(base.get("mediaport")),
        rtsp_port=_to_int(base.get("rtspport")),
        rtsp_url=_to_str(base.get("rtspurl")),
        handset_port=_to_int(base.get("handsetport")),
        max_users=_to_int(base.get("maxusers")),
        transfer_mode=_to_bool(base.get("transfermode")),
        hs_download=_to_bool(base.get("hsdownload")),
        ability=(
            DeviceNetworkBaseAbility(
                valid=_to_int(ability.get("valid")),
                support_dhcp=_to_int(ability.get("support_dhcp")),
                support_inner_ip=_to_int(ability.get("support_innerip")),
                support_multi_eth=_to_int(ability.get("support_multi_eth")),
            )
            if ability
            else None
        ),
        transfer_policy=(
            DeviceNetworkTransferPolicy(
                value=_to_str(transfer_policy.get("value")),
                supported=_to_str(transfer_policy.get("supported")),
            )
            if transfer_policy
            else None
        ),
        lan_interfaces=[
            _parse_lan_info(_as_dict(item).get("lan", item))
            for item in _data_items(base.get("lanlist"))
        ],
        content=response.content,
        raw=response,
    )


def parse_system_general_info(
    response: DeviceCgiResponse,
) -> DeviceGeneralInfo:
    """Map `get.system.general` content into `DeviceGeneralInfo`."""

    general = _as_dict(_lookup(response.content, "system", "general"))
    ability = _as_dict(general.get("ability"))
    return DeviceGeneralInfo(
        error=response.error,
        language=_to_str(_value_of(general.get("language"))),
        auto_sync_time=_to_bool(general.get("autosynctime")),
        time_zone=_to_str(general.get("timezone")),
        date_time=_to_str(general.get("datetime")),
        device_id=_to_str(general.get("deviceid")),
        host_name=_to_str(_value_of(general.get("hostname"))),
        date_split=_to_str(general.get("datesplit")),
        date_format=_to_str(general.get("dateformat")),
        time_format=_to_str(general.get("timeformat")),
        on_storage_full=_to_str(general.get("onstoragefull")),
        video_standard=_to_str(general.get("videostandard")),
        auto_logout=_to_int(general.get("autologout")),
        startup_wizard=_to_bool(general.get("startupwizard")),
        smart_display=_to_bool(general.get("smartdisplay")),
        smart_tracking=_to_bool(general.get("smarttracking")),
        preview_strategy=_to_str(general.get("previewstrategy")),
        support_host_name=_to_bool(ability.get("support_hostname")),
        content=general,
        raw=response,
    )


def parse_system_capabilities(
    response: DeviceCgiResponse,
) -> DeviceCapabilitiesInfo:
    """Map `get.system.ability` content into `DeviceCapabilitiesInfo`."""

    ability = _as_dict(_lookup(response.content, "system", "ability"))
    optional = _as_dict(_lookup(ability, "optional", "mask_0"))
    alarm_ability = _as_dict(_lookup(ability, "alarm", "alarmability"))
    return DeviceCapabilitiesInfo(
        error=response.error,
        wifi=_to_int(optional.get("ability_wifi")),
        rtsp=_to_int(optional.get("ability_rtsp")),
        snap=_to_int(optional.get("ability_snap")),
        talk=_to_int(_lookup(ability, "talk", "ability")),
        ptz=_to_int(optional.get("ability_ptz")),
        ptz_preset=_to_int(optional.get("ability_ptz_preset")),
        https=_to_int(optional.get("ability_https")),
        ntp=_to_int(optional.get("ability_ntp")),
        cloud=_to_int(optional.get("ability_cloud")),
        cloud_storage=_to_int(optional.get("ability_cloudstorage")),
        cloud_upgrade=_to_int(optional.get("ability_cloud_upgrade")),
        automatic_ip=_to_int(optional.get("ability_automatic_ip")),
        motion_detection=_to_int(
            alarm_ability.get("motiondetection")
            or alarm_ability.get("motion_detect")
        ),
        alarm_in=_to_int(alarm_ability.get("alarmin")),
        video_lost=_to_int(alarm_ability.get("videolost")),
        video_shelter=_to_int(alarm_ability.get("videoshelter")),
        content=ability,
        raw=response,
    )


def parse_video_config_info(
    response: DeviceCgiResponse,
) -> DeviceVideoConfigInfo:
    """Map `get.encode` content into `DeviceVideoConfigInfo`."""

    channels = [
        _parse_video_channel(_as_dict(item))
        for item in _data_items(response.content.get("channel"))
    ]
    return DeviceVideoConfigInfo(
        error=response.error,
        channels=channels,
        content=response.content,
        raw=response,
    )


def parse_device_all_info(response: DeviceCgiResponse) -> DeviceAllInfo:
    """Extract stable fields from broad `get.device.status` content."""

    info = _as_dict(response.content.get("info"))
    network = _as_dict(response.content.get("network"))
    wifi = _as_dict(response.content.get("wifiinfo"))
    status = _as_dict(response.content.get("devicestatus"))
    tfcard = _as_dict(response.content.get("tfcard"))
    time_info = _as_dict(response.content.get("time"))
    return DeviceAllInfo(
        error=response.error,
        model=_to_str(info.get("model")),
        version=_to_str(
            info.get("version") or response.content.get("version")
        ),
        release_date=_to_str(info.get("releasedate")),
        latest_version=_to_str(response.content.get("version")),
        latest_release_date=_to_str(response.content.get("releasetime")),
        mac=_to_str(
            info.get("mac") or network.get("mac") or status.get("mac")
        ),
        ssid=_to_str(wifi.get("ssid")),
        rssi=_to_int(wifi.get("rssi") or status.get("rssi")),
        time_zone=_to_str(time_info.get("timezone")),
        total_sum=_to_int(tfcard.get("totalsum")),
        free_sum=_to_int(tfcard.get("freesum")),
        content=response.content,
        raw=response,
    )


def _parse_attachment_channel(
    value: dict[str, Any],
) -> DeviceAttachmentChannel:
    return DeviceAttachmentChannel(
        channel_id=_to_int(value.get("num")),
        name=_to_str(value.get("name")),
        channel_type=_to_str(value.get("type")),
        sub_type=_attachment_channel_sub_type(_to_str(value.get("type"))),
        enabled=_to_bool(value.get("enable"), default=True),
        video_enabled=_to_bool(value.get("monenable"), default=True),
        talk_enabled=_to_bool(value.get("talkenable")),
        cctv_type=_to_int(value.get("cctvtype")),
        locks=[
            DeviceAttachmentLock(
                lock_id=_to_int(_as_dict(item).get("num")),
                name=_to_str(_as_dict(item).get("name")),
                enabled=_to_bool(_as_dict(item).get("enable")),
            )
            for item in _named_items(value.get("lockinfo"), "lock")
        ],
    )


def _parse_tf_card_disk(value: dict[str, Any]) -> DeviceTfCardDiskInfo:
    status_raw = _to_str(value.get("status"))
    return DeviceTfCardDiskInfo(
        exists=_to_bool(value.get("exist"), default=False) or False,
        disk_id=_to_int(value.get("diskid")),
        status=_tf_card_status_code(status_raw),
        status_raw=status_raw,
        total=_to_int(value.get("total")),
        free=_to_int(value.get("free")),
    )


def _tf_card_status_code(value: str) -> int:
    return {
        "notformatted": 1,
        "error": 2,
        "sleep": 3,
        "normal": 4,
        "nodisk": 5,
    }.get(value.strip().lower(), -1)


def _attachment_channel_sub_type(channel_type: str) -> int:
    return {
        "cam": 0,
        "cctv": 1,
        "ipg": 2,
        "manage": 3,
        "ep": 4,
        "iot": 5,
        "telephone": 6,
    }.get(channel_type, 0)


def _parse_video_channel(value: dict[str, Any]) -> DeviceVideoChannelInfo:
    stream_names = ("mainstream", "substream", "alarmstream", "thirdstream")
    streams = [
        _parse_video_stream(stream_name, _as_dict(value.get(stream_name)))
        for stream_name in stream_names
        if value.get(stream_name) is not None
    ]
    return DeviceVideoChannelInfo(
        channel_id=_to_str(value.get("id")),
        name=_to_str(value.get("name")),
        ability=_to_str(value.get("ability")),
        encode_new=_to_bool(value.get("encode_new")),
        video_mode=_to_str(value.get("videomode")),
        protocol=_to_str(value.get("protocol")),
        streams=streams,
        raw=value,
    )


def _parse_video_stream(
    name: str,
    value: dict[str, Any],
) -> DeviceVideoStreamInfo:
    video_format = _as_dict(value.get("videoformat"))
    return DeviceVideoStreamInfo(
        name=name,
        enabled=_to_bool(video_format.get("enabled")),
        compression=_to_str(_value_of(video_format.get("compression"))),
        resolution=_to_str(_value_of(video_format.get("resolution"))),
        bitrate=_to_int(_value_of(video_format.get("bitrate"))),
        bitrate_control=_to_str(_value_of(video_format.get("bitratecontrol"))),
        fps=_to_int(_value_of(video_format.get("fps"))),
        gop=_to_int(_value_of(video_format.get("gop"))),
        quality=_to_int(_value_of(video_format.get("quality"))),
        audio_enabled=_to_bool(_lookup(value, "audioformat", "enabled")),
        h264plus_enabled=_to_bool(_lookup(value, "h264plus", "enabled")),
        raw=value,
    )


def _parse_lan_info(value: Any) -> DeviceLanInfo:
    lan = _as_dict(value)
    network_type = _as_dict(lan.get("nctype"))
    return DeviceLanInfo(
        name=_to_str(lan.get("name")),
        ip_address=_to_str(lan.get("ipaddress")),
        subnet_mask=_to_str(lan.get("subnetmask")),
        gateway=_to_str(lan.get("gateway")),
        mac=_to_str(lan.get("mac")),
        dhcp=_to_bool(lan.get("dhcp")),
        network_type=_to_str(network_type.get("value")),
        supported_network_types=_to_str(network_type.get("supported")),
    )


def _parse_time_title_overlay(
    value: dict[str, Any],
) -> DeviceTimeTitleOverlay:
    return DeviceTimeTitleOverlay(
        stream_type=_to_int(value.get("streamtype")),
        video_width=_to_int(value.get("videowidth")),
        video_height=_to_int(value.get("videoheight")),
        title_width=_to_int(value.get("titlewidth")),
        title_height=_to_int(value.get("titleheight")),
        location_x=_to_int(value.get("x")),
        location_y=_to_int(value.get("y")),
    )


def _parse_record_schedule_day(
    value: dict[str, Any],
) -> list[DeviceRecordScheduleTime]:
    entries: list[DeviceRecordScheduleTime] = []
    for slot in range(1, 7):
        item = _as_dict(value.get(f"time{slot}"))
        if not item:
            continue
        entries.append(
            DeviceRecordScheduleTime(
                slot=slot,
                record_type=_to_str(item.get("type")),
                start=_to_str(item.get("start")),
                end=_to_str(item.get("end")),
            )
        )
    return entries


def _parse_record_file(value: dict[str, Any]) -> DeviceRecordFileInfo:
    return DeviceRecordFileInfo(
        record_id=_to_str(value.get("id")),
        file_name=_first_str(value, "filename", "fileName", "name"),
        file_type=_first_str(value, "filetype", "file_type", "type"),
        occur_type=_first_str(value, "occurtype", "recordtype", "record_type"),
        channel_id=_first_str(value, "channel", "channels", "ch", "chno"),
        start_time=_first_str(value, "starttime", "start_time", "start"),
        end_time=_first_str(value, "endtime", "end_time", "end"),
        stream=_first_str(value, "stream", "streamtype", "stream_type"),
        file_size=_to_int(
            _first_present(value, "filesize", "fileSize", "size")
        ),
        url=_to_str(value.get("url")),
        raw=value,
    )


def _record_message_items(content: dict[str, Any]) -> list[Any]:
    candidates = [
        content.get("record"),
        _lookup(content, "recordlist", "record"),
        _lookup(content, "records", "record"),
        _lookup(content, "filelist", "file"),
        _lookup(content, "files", "file"),
        _lookup(content, "datalist", "data"),
    ]
    for candidate in candidates:
        items = _named_items(candidate, "record", "file", "data")
        if items:
            return items
    return []


def _parse_alarm_channel(value: dict[str, Any]) -> DeviceAlarmChannel:
    return DeviceAlarmChannel(
        channel_id=_to_int(value.get("id")),
        name=_to_str(value.get("name")),
        channel_type=_to_str(value.get("channeltype")),
        serial_no=_to_int(value.get("serialno")),
    )


def _parse_alarm_input_channel(
    value: dict[str, Any],
) -> DeviceAlarmInputChannel:
    alarm_input = _as_dict(value.get("alarmin"))
    return DeviceAlarmInputChannel(
        channel_id=_to_int(value.get("id")),
        enabled=_to_bool(alarm_input.get("enabled")),
        input_type=_to_str(alarm_input.get("type")),
        name=_to_str(alarm_input.get("name")),
    )


def _parse_alarm_schedule_info(
    response: DeviceCgiResponse,
    alarm_type: str,
) -> DeviceAlarmScheduleInfo:
    channel = _as_dict(response.content.get("channel"))
    schedule = _as_dict(_lookup(channel, alarm_type, "schedule"))
    return DeviceAlarmScheduleInfo(
        error=response.error,
        alarm_type=alarm_type,
        channel_id=_to_int(channel.get("id")),
        days={
            day: _parse_alarm_schedule_day(day, _as_dict(schedule.get(day)))
            for day in _ALARM_SCHEDULE_DAYS
        },
        content=response.content,
        raw=response,
    )


def _parse_alarm_schedule_day(
    day: str,
    value: dict[str, Any],
) -> DeviceAlarmScheduleDay:
    slots: list[DeviceAlarmScheduleSlot] = []
    for slot in range(1, 7):
        item = _as_dict(value.get(f"time{slot}"))
        if not item:
            continue
        slots.append(
            DeviceAlarmScheduleSlot(
                slot=slot,
                enabled=_to_bool(item.get("enabled")),
                start=_normalize_alarm_schedule_start(
                    _to_str(item.get("start"))
                ),
                end=_normalize_alarm_schedule_end(_to_str(item.get("end"))),
            )
        )
    return DeviceAlarmScheduleDay(day=day, slots=slots)


def _normalize_alarm_schedule_start(value: str) -> str:
    return "00:00:00" if value == "0:0:0" else value


def _normalize_alarm_schedule_end(value: str) -> str:
    return "23:59:59" if value in {"24:0:0", "24:00:00"} else value


def _alarm_channel_items(content: dict[str, Any]) -> list[Any]:
    candidates = [
        content.get("channel"),
        _lookup(content, "channellist", "channel"),
        _lookup(content, "channels", "channel"),
        _lookup(content, "datalist", "data"),
    ]
    for candidate in candidates:
        items = _named_items(candidate, "channel", "data")
        if items:
            return items
    return []


def _select_response_channels(
    response_channels: list[dict[str, Any]],
    channel_id: int,
) -> list[dict[str, Any]]:
    if channel_id == -1:
        return response_channels
    if 0 <= channel_id < len(response_channels):
        return [response_channels[channel_id]]
    return response_channels[:1]


def _select_response_fps_values(
    fps_values: list[int],
    stream_id: int,
) -> list[int]:
    if stream_id == -1:
        return fps_values
    if 0 <= stream_id < len(fps_values):
        return [fps_values[stream_id]]
    return fps_values[:1]


def _fps_values(value: Any) -> list[int]:
    values = value if isinstance(value, list) else [value]
    return [fps for item in values if (fps := _to_int(item)) is not None]


def _range_bounds(value: str) -> tuple[int | None, int | None]:
    left, _, right = value.partition(",")
    return _to_int(left), _to_int(right)


def _children_to_dict(element: ET.Element) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for child in list(element):
        value = _element_to_value(child)
        current = result.get(child.tag)
        if current is None:
            result[child.tag] = value
        elif isinstance(current, list):
            current.append(value)
        else:
            result[child.tag] = [current, value]
    return result


def _element_to_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    return _children_to_dict(element)


def _lookup(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        current = _as_dict(current).get(key)
    return current


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _data_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        data = (
            value.get("data")
            or value.get("wifi")
            or value.get("lanlist")
            or value.get("lan")
        )
        if isinstance(data, list):
            return data
        if data is not None:
            return [data]
    if value is None:
        return []
    return [value]


def _named_items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for name in names:
            item = value.get(name)
            if isinstance(item, list):
                return item
            if item is not None:
                return [item]
        return _data_items(value)
    if value is None:
        return []
    return [value]


def _value_of(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value")
    return value


def _first_present(value: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return None


def _first_str(value: dict[str, Any], *names: str) -> str:
    return _to_str(_first_present(value, *names))


def _to_str(value: Any) -> str:
    return "" if value is None else str(value)


def _to_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, *, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _rotation_angle(value: str) -> int:
    return {
        "r90": 90,
        "r180": 180,
        "r270": 270,
    }.get(value, 0)

"""XML parsing helpers for read-only `/tdkcgi` responses."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from quii_helper.device.cgi.models import (
    DeviceAllInfo,
    DeviceCapabilitiesInfo,
    DeviceCgiResponse,
    DeviceGeneralInfo,
    DeviceLanInfo,
    DeviceNetworkInfo,
    DeviceProductInfo,
    DeviceScreenFlipInfo,
    DeviceStorageDisk,
    DeviceStorageInfo,
    DeviceTimeInfo,
    DeviceTimeTitleInfo,
    DeviceTimeTitleOverlay,
    DeviceVideoChannelInfo,
    DeviceVideoConfigInfo,
    DeviceVideoStreamInfo,
    DeviceVideoSwitchInfo,
    DeviceWifiListInfo,
    DeviceWifiNetwork,
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
    return DeviceLanInfo(
        name=_to_str(lan.get("name")),
        ip_address=_to_str(lan.get("ipaddress")),
        subnet_mask=_to_str(lan.get("subnetmask")),
        gateway=_to_str(lan.get("gateway")),
        mac=_to_str(lan.get("mac")),
        dhcp=_to_bool(lan.get("dhcp")),
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


def _value_of(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value")
    return value


def _to_str(value: Any) -> str:
    return "" if value is None else str(value)


def _to_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _rotation_angle(value: str) -> int:
    return {
        "r90": 90,
        "r180": 180,
        "r270": 270,
    }.get(value, 0)

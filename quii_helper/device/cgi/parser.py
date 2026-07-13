"""XML parsing helpers for read-only `/tdkcgi` responses."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from quii_helper.device.cgi.models import (
    DeviceAllInfo,
    DeviceCgiResponse,
    DeviceLanInfo,
    DeviceNetworkInfo,
    DeviceStorageDisk,
    DeviceStorageInfo,
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
        data = value.get("data") or value.get("lanlist") or value.get("lan")
        if isinstance(data, list):
            return data
        if data is not None:
            return [data]
    if value is None:
        return []
    return [value]


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

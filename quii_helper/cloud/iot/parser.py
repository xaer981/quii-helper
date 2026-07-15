import json
from collections.abc import Mapping
from typing import Any

from quii_helper.cloud.iot.models import CameraIotCommandSupportInfo
from quii_helper.support.errors import QuiiConnectionError

COMMAND_OPEN_LOCK = "set.device.opendoor"
COMMAND_GET_RPC_COMMAND_LIST = "get.rrpc.commandlist"
COMMAND_GET_FLOODLIGHT_SWITCH = "get.floodlight.switch"
COMMAND_SET_FLOODLIGHT_SWITCH = "set.floodlight.switch"
COMMAND_GET_ALARM_CONFIG = "get.alarm.detailInfo"
COMMAND_SET_ALARM_CONFIG = "set.alarm.detailInfo"

_SUPPORT_COMMAND_BITS = (
    (0, COMMAND_OPEN_LOCK),
    (1, COMMAND_GET_FLOODLIGHT_SWITCH),
    (2, COMMAND_SET_FLOODLIGHT_SWITCH),
    (3, COMMAND_GET_ALARM_CONFIG),
    (4, COMMAND_SET_ALARM_CONFIG),
)


def parse_iot_command_support(
    payload: Mapping[str, Any],
) -> CameraIotCommandSupportInfo:
    """Parse native-compatible IoT `get.rrpc.commandlist` response."""

    outer = dict(payload)
    inner = _payload_mapping(outer)
    content = _mapping(inner.get("content"))
    commands = tuple(
        str(command)
        for command in _sequence(content.get("commandlist"))
        if str(command)
    )
    support_mask = _support_mask(commands)
    raw = dict(outer)
    if inner:
        raw["parsed_payload"] = dict(inner)

    return CameraIotCommandSupportInfo(
        result=_int(outer.get("result"), default=0 if inner else -1),
        error=_int(inner.get("error"), default=-1),
        message=str(outer.get("message") or ""),
        commands=commands,
        support_mask=support_mask,
        supports_open_lock=_has_support(support_mask, 0),
        supports_floodlight_read=_has_support(support_mask, 1),
        supports_floodlight_write=_has_support(support_mask, 2),
        supports_alarm_config_read=_has_support(support_mask, 3),
        supports_alarm_config_write=_has_support(support_mask, 4),
        raw=raw,
    )


def _payload_mapping(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = payload.get("payload")
    if isinstance(nested, str) and nested:
        try:
            decoded = json.loads(nested)
        except json.JSONDecodeError as exc:
            raise QuiiConnectionError(
                "IoT command support payload is not JSON"
            ) from exc
        return _mapping(decoded)
    if isinstance(nested, Mapping):
        return nested
    if "error" in payload or "content" in payload:
        return payload
    return {}


def _support_mask(commands: tuple[str, ...]) -> int:
    command_set = set(commands)
    mask = 0
    for bit, command in _SUPPORT_COMMAND_BITS:
        if command in command_set:
            mask |= 1 << bit
    return mask


def _has_support(mask: int, bit: int) -> bool:
    return bool(mask & (1 << bit))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, list | tuple):
        return tuple(value)
    return ()


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

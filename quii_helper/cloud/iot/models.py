from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CameraIotCommandSupportInfo:
    """IoT/RRPC command support reported by the cloud control service.

    Attributes:
        result: Outer cloud IoT result code.
        error: Inner device command error code.
        message: Outer cloud IoT message.
        commands: Native command names returned by `get.rrpc.commandlist`.
        support_mask: Native-compatible support bit mask.
        supports_open_lock: Whether `set.device.opendoor` is advertised.
        supports_floodlight_read: Whether `get.floodlight.switch` is advertised.
        supports_floodlight_write: Whether `set.floodlight.switch` is advertised.
        supports_alarm_config_read: Whether `get.alarm.detailInfo` is advertised.
        supports_alarm_config_write: Whether `set.alarm.detailInfo` is advertised.
        raw: Full raw JSON response, including the parsed payload when present.
    """

    result: int
    error: int
    message: str
    commands: tuple[str, ...]
    support_mask: int
    supports_open_lock: bool
    supports_floodlight_read: bool
    supports_floodlight_write: bool
    supports_alarm_config_read: bool
    supports_alarm_config_write: bool
    raw: dict[str, Any]

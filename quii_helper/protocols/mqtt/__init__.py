"""MQTT bootstrap helpers for P2P session setup."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MqttP2PBootstrap": (
        "quii_helper.protocols.mqtt.bootstrap",
        "MqttP2PBootstrap",
    ),
    "ParsedMqttUrl": ("quii_helper.protocols.mqtt.url", "ParsedMqttUrl"),
    "ensure_mqtt_runtime": (
        "quii_helper.protocols.mqtt.runtime",
        "ensure_mqtt_runtime",
    ),
    "parse_mqtt_url": ("quii_helper.protocols.mqtt.url", "parse_mqtt_url"),
    "reset_mqtt_runtime": (
        "quii_helper.protocols.mqtt.runtime",
        "reset_mqtt_runtime",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value

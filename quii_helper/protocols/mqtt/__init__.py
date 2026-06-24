"""MQTT bootstrap helpers for P2P session setup."""

from quii_helper.support.lazy import lazy_exports

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

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())

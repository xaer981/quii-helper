"""Protocol implementations used by the preview and probe flows."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DirectKcpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "DirectKcpQuiiTunnel",
    ),
    "MqttP2PBootstrap": (
        "quii_helper.protocols.mqtt.bootstrap",
        "MqttP2PBootstrap",
    ),
    "P2PConnectRequest": (
        "quii_helper.protocols.p2p.protocol",
        "P2PConnectRequest",
    ),
    "P2PConnectResponse": (
        "quii_helper.protocols.p2p.protocol",
        "P2PConnectResponse",
    ),
    "QuiiClient": ("quii_helper.protocols.tcp.client", "QuiiClient"),
    "RbUdpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "RbUdpQuiiTunnel",
    ),
    "TcpProbeRunner": ("quii_helper.protocols.tcp.runner", "TcpProbeRunner"),
    "aes_cbc_crypt": ("quii_helper.protocols.quii.crypto", "aes_cbc_crypt"),
    "build_live_keepalive_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_keepalive_packet",
    ),
    "build_live_play_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_play_packet",
    ),
    "build_live_setup_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_setup_packet",
    ),
    "create_request_session_id": (
        "quii_helper.protocols.p2p.protocol",
        "create_request_session_id",
    ),
    "create_session_flag": (
        "quii_helper.protocols.p2p.protocol",
        "create_session_flag",
    ),
    "decode_quii_blob": (
        "quii_helper.protocols.quii.blob",
        "decode_quii_blob",
    ),
    "decode_ust_mqtt_credentials": (
        "quii_helper.protocols.ust.credentials",
        "decode_ust_mqtt_credentials",
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

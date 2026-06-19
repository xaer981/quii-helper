"""TCP client and probe helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "QuiiClient": ("quii_helper.protocols.tcp.client", "QuiiClient"),
    "QuiiLiveOpenPacketBuilder": (
        "quii_helper.protocols.tcp.live_packet_builder",
        "QuiiLiveOpenPacketBuilder",
    ),
    "QuiiTcpProbeRunner": (
        "quii_helper.protocols.tcp.quii_probe",
        "QuiiTcpProbeRunner",
    ),
    "TcpLiveProbeCapture": (
        "quii_helper.protocols.tcp.live_probe_capture",
        "TcpLiveProbeCapture",
    ),
    "TcpProbeRunner": ("quii_helper.protocols.tcp.runner", "TcpProbeRunner"),
    "TcpSocketTransport": (
        "quii_helper.protocols.tcp.transport",
        "TcpSocketTransport",
    ),
    "run_quii_probe": (
        "quii_helper.protocols.tcp.quii_probe",
        "run_quii_probe",
    ),
    "settings": ("quii_helper.protocols.tcp.settings", None),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    module = import_module(module_name)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value

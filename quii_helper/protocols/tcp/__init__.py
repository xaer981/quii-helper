"""TCP client and probe helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "QuiiClient": ("quii_helper.protocols.tcp.transport.client", "QuiiClient"),
    "QuiiLiveOpenPacketBuilder": (
        "quii_helper.protocols.tcp.live.packet_builder",
        "QuiiLiveOpenPacketBuilder",
    ),
    "QuiiTcpProbeRunner": (
        "quii_helper.protocols.tcp.probes.quii_probe",
        "QuiiTcpProbeRunner",
    ),
    "TcpLiveProbeCapture": (
        "quii_helper.protocols.tcp.live.probe_capture",
        "TcpLiveProbeCapture",
    ),
    "TcpProbeRunner": (
        "quii_helper.protocols.tcp.probes.runner",
        "TcpProbeRunner",
    ),
    "TcpSocketTransport": (
        "quii_helper.protocols.tcp.transport.socket_transport",
        "TcpSocketTransport",
    ),
    "run_quii_probe": (
        "quii_helper.protocols.tcp.probes.quii_probe",
        "run_quii_probe",
    ),
    "settings": ("quii_helper.protocols.tcp.probes.settings", None),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())

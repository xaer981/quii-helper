from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "DirectKcpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel.session",
        "DirectKcpQuiiTunnel",
    ),
    "RbUdpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel.session",
        "RbUdpQuiiTunnel",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())

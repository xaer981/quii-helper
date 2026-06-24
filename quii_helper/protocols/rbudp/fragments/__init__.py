from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "RbUdpWrappedFragmentAssembler": (
        "quii_helper.protocols.rbudp.fragments.flow",
        "RbUdpWrappedFragmentAssembler",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())

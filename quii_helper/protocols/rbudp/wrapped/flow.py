"""Backward-compatible RB-UDP wrapped flow mixin."""

from quii_helper.protocols.rbudp.wrapped.handler import (
    RbUdpWrappedHandlerMixin,
)
from quii_helper.protocols.rbudp.wrapped.sender import RbUdpWrappedSenderMixin


class RbUdpWrappedFlowMixin(RbUdpWrappedHandlerMixin, RbUdpWrappedSenderMixin):
    pass

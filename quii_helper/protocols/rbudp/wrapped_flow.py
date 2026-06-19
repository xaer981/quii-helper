"""Backward-compatible RB-UDP wrapped flow mixin."""

from quii_helper.protocols.rbudp.wrapped_handler import (
    RbUdpWrappedHandlerMixin,
)
from quii_helper.protocols.rbudp.wrapped_sender import RbUdpWrappedSenderMixin


class RbUdpWrappedFlowMixin(RbUdpWrappedHandlerMixin, RbUdpWrappedSenderMixin):
    pass

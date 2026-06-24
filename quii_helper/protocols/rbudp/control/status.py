from quii_helper.protocols.rbudp.control.ack_status import (
    RbUdpControlAckStatusMixin,
)
from quii_helper.protocols.rbudp.control.handshake import (
    RbUdpControlHandshakeMixin,
)
from quii_helper.protocols.rbudp.control.lane_updates import (
    RbUdpControlLaneUpdateMixin,
)
from quii_helper.protocols.rbudp.control.play_status import (
    RbUdpControlPlayStatusMixin,
)
from quii_helper.protocols.rbudp.control.progress import (
    RbUdpControlProgressMixin,
)


class RbUdpControlStatusMixin(
    RbUdpControlHandshakeMixin,
    RbUdpControlLaneUpdateMixin,
    RbUdpControlProgressMixin,
    RbUdpControlAckStatusMixin,
    RbUdpControlPlayStatusMixin,
):
    pass

from quii_helper.protocols.rbudp.control_ack_status import (
    RbUdpControlAckStatusMixin,
)
from quii_helper.protocols.rbudp.control_handshake import (
    RbUdpControlHandshakeMixin,
)
from quii_helper.protocols.rbudp.control_lane_updates import (
    RbUdpControlLaneUpdateMixin,
)
from quii_helper.protocols.rbudp.control_play_status import (
    RbUdpControlPlayStatusMixin,
)
from quii_helper.protocols.rbudp.control_progress import (
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

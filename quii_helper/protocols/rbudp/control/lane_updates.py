from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlLaneUpdateMixin:
    def _apply_control_lane_ids(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> int:
        if control.remote_id and control.remote_id not in (0xFFFFFFFF, 1):
            lane["peer_logic_id"] = control.remote_id
        return int(lane["peer_logic_id"])

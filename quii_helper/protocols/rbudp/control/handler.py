from quii_helper.protocols.rbudp.control.dispatcher import (
    EventLike,
    RbUdpControlDispatcher,
    RbUdpControlDispatcherOwner,
)
from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlHandler:
    """Dispatch parsed RBUDP control packets to control status handlers."""

    def __init__(self, owner: RbUdpControlDispatcherOwner) -> None:
        self._owner = owner
        self._dispatcher = RbUdpControlDispatcher(owner)

    def handle_control(self, control: ParsedRbUdpControlPacket) -> None:
        self._dispatcher.handle(control)

    def is_quii_play_ack_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status16: int,
    ) -> bool:
        owner = self._owner
        if status16 != (owner.CONTROL_ESTABLISHED_STATUS & 0xFFFF):
            return False
        if not owner._quii_play_sent.is_set() or bool(lane["quii_play_acked"]):
            return False
        play_end_local_id = int(lane.get("quii_play_end_local_id", 0))
        return (
            play_end_local_id > 0
            and control.remote_id == play_end_local_id
            and control.local_id > 1
        )

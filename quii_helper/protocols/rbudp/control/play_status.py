from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlPlayStatusMixin:
    def _handle_play_late_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._dbg(
            "recv_control_play_late_status",
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=control.local_id,
            remote_id=control.remote_id,
        )

    def _handle_play_sync_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._start_play_sync(
            lane,
            local_id=(
                control.remote_id if control.remote_id else control.local_id
            ),
            seed_remote_id=(control.local_id + self.CONTROL_PLAY_SYNC_STEP)
            & 0xFFFFFFFF,
        )

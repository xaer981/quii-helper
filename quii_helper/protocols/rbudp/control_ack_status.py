from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.models import ParsedRbUdpControlPacket


class RbUdpControlAckStatusMixin:
    def _send_offset_ack(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status_word: int,
        remote_delta: int,
        log_label: str,
    ) -> tuple[int, int]:
        current_local = int(lane["local_id"])
        next_local = current_local if current_local else control.remote_id
        remote_base = (
            control.remote_id if control.remote_id else int(lane["remote_id"])
        )
        next_remote = (remote_base + remote_delta) & 0xFFFFFFFF
        self._send_lane_control(
            lane,
            status_word=status_word,
            local_id=next_local,
            remote_id=next_remote,
            log_label=log_label,
        )
        lane["local_id"] = next_local
        lane["remote_id"] = next_remote
        return next_local, next_remote

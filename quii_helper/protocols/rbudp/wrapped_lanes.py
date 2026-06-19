from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.models import ParsedRbUdpWrappedPacket


class RbUdpWrappedLaneMixin:
    _lane_states: list[RbUdpLane]

    def _lane_for_wrapped(
        self, wrapped: ParsedRbUdpWrappedPacket
    ) -> RbUdpLane | None:
        for candidate in self._lane_states:
            candidate_word4 = int(candidate["word4"])
            candidate_word8 = int(candidate["word8"])
            if (
                candidate_word4 == wrapped.word4
                and candidate_word8 == wrapped.word8
            ) or (
                candidate_word8 == wrapped.word4
                and candidate_word4 == wrapped.word8
            ):
                return candidate
        return None

    def _refresh_lane_from_wrapped(
        self, lane: RbUdpLane, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        if wrapped.local_id and not int(lane["local_id"]):
            lane["local_id"] = wrapped.local_id
        if wrapped.remote_id and not int(lane["remote_id"]):
            lane["remote_id"] = wrapped.remote_id
        peer_logic_id = int(lane["peer_logic_id"])
        if (
            wrapped.tag8 == self.CONNECT_TAG
            and peer_logic_id
            and not bool(lane["progress_sent"])
        ):
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_PROGRESS_STATUS,
                local_id=peer_logic_id,
                remote_id=peer_logic_id,
                log_label="send_control_progress",
            )
            lane["progress_sent"] = True

from typing import Protocol

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpWrappedLaneOwner(Protocol):
    CONNECT_TAG: bytes
    CONTROL_PROGRESS_STATUS: int
    _lane_states: list[RbUdpLane]

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
    ) -> None: ...


class RbUdpWrappedLaneState:
    """Find and refresh RBUDP lanes from inbound wrapped packets."""

    def __init__(self, owner: RbUdpWrappedLaneOwner) -> None:
        self._owner = owner

    def lane_for_wrapped(
        self, wrapped: ParsedRbUdpWrappedPacket
    ) -> RbUdpLane | None:
        for candidate in self._owner._lane_states:
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

    def refresh_lane_from_wrapped(
        self, lane: RbUdpLane, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        owner = self._owner
        if wrapped.local_id and not int(lane["local_id"]):
            lane["local_id"] = wrapped.local_id
        if wrapped.remote_id and not int(lane["remote_id"]):
            lane["remote_id"] = wrapped.remote_id
        peer_logic_id = int(lane["peer_logic_id"])
        if (
            wrapped.tag8 == owner.CONNECT_TAG
            and peer_logic_id
            and not bool(lane["progress_sent"])
        ):
            owner._send_lane_control(
                lane,
                status_word=owner.CONTROL_PROGRESS_STATUS,
                local_id=peer_logic_id,
                remote_id=peer_logic_id,
                log_label="send_control_progress",
            )
            lane["progress_sent"] = True

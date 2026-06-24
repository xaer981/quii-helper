from collections.abc import Callable

from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane

DebugCallback = Callable[..., None]
LaneLookupCallback = Callable[..., RbUdpLane | None]
FragmentAckCallback = Callable[..., None]


class RbUdpFragmentAckCoordinator:
    def __init__(
        self,
        *,
        debug: DebugCallback,
        lane_for_packet_words: LaneLookupCallback,
        send_fragment_ack: FragmentAckCallback,
    ) -> None:
        self.debug = debug
        self.lane_for_packet_words = lane_for_packet_words
        self.send_fragment_ack = send_fragment_ack

    def ack_stream(
        self,
        stream: RbUdpWrappedFragmentStream,
        *,
        reason: str,
        force: bool = False,
        log_label: str = "send_control_fragment_ack",
    ) -> None:
        if not force and stream.last_ack_remote_id == stream.next_local_id:
            return
        lane = self.lane_for_packet_words(
            word4=stream.word4,
            word8=stream.word8,
        )
        if lane is None:
            self.debug(
                "skip_wrapped_fragment_ack_no_lane",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                next_local_id=stream.next_local_id,
                reason=reason,
            )
            return
        self.send_fragment_ack(
            lane,
            stream.remote_id,
            stream.next_local_id,
            word4=stream.word8,
            word8=stream.word4,
            log_label=log_label,
        )
        stream.last_ack_remote_id = stream.next_local_id

from quii_helper.protocols.rbudp.control.flow import RbUdpControlFlow
from quii_helper.protocols.rbudp.control.handshake import (
    RbUdpControlHandshake,
)
from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


def _lane() -> RbUdpLane:
    return {
        "src_id": 0x4000006,
        "bootstrap_word4": 0,
        "bootstrap_word8": 0x01000000,
        "bootstrap_local_id": 0,
        "bootstrap_remote_id": 0,
        "word4": 0,
        "word8": 0,
        "peer_word4": 0,
        "peer_word8": 0,
        "local_id": 0,
        "remote_id": 0,
        "nonce": 0,
        "progress_sent": True,
        "flow_sent": True,
        "established_sent": False,
        "syn_ack_received": False,
        "post_play_established_sent": True,
        "play_probe_stage": 3,
        "play_sync_active": True,
        "play_sync_local_id": 1,
        "play_sync_counter": 2,
        "play_sync_remaining": 3,
        "play_sync_sent_count": 4,
        "play_sync_remote_bias": 5,
        "play_word_refresh_sent": True,
        "play_transport_refresh_sent": True,
        "peer_logic_id": 99,
    }


def _syn_ack() -> ParsedRbUdpControlPacket:
    return ParsedRbUdpControlPacket(
        marker=0xFFABEFC1,
        word4=0x01000000,
        word8=0x0F000007,
        local_id=0,
        remote_id=1,
        status_word=RbUdpProtocolConstants.CONTROL_SYN_ACK_STATUS,
        rand16=0,
        packet_len16=28,
    )


class _Owner(RbUdpProtocolConstants):
    def __init__(self) -> None:
        self._peer_addr = ("127.0.0.1", 59318)
        self._bootstrap_sent_to = None
        self._forced_transition = False
        self.local_id = 0
        self.remote_id = 0
        self.word4 = 0
        self.word8 = 0
        self.src_ids = [0x4000006]
        self._lane_states = [_lane()]
        self.sent: list[bytes] = []
        self.wrapped_connects: list[RbUdpLane] = []
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.control_flow = RbUdpControlFlow(self)
        self.control_handshake = RbUdpControlHandshake(self)

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        return 0x1234

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _send_udp(self, packet: bytes) -> None:
        self.sent.append(packet)

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None:
        self.wrapped_connects.append(lane)

    def _send_pending_established(self) -> None:
        self.control_flow.send_pending_established()

    def _lane_for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        if control.word4 == self._lane_states[0]["bootstrap_word8"]:
            return self._lane_states[0]
        return None


class RbUdpControlHandshakeFlowTests:
    def test_syn_ack_transition_sends_established_when_all_lanes_ready(
        self,
    ) -> None:
        owner = _Owner()
        lane = owner._lane_states[0]

        handled = owner.control_handshake.handle_syn_ack_control(_syn_ack())

        assert handled
        assert 0x0F000007 == lane["word4"]
        assert 0x01000000 == lane["word8"]
        assert 1 == lane["local_id"]
        assert 1 == lane["remote_id"]
        assert lane["syn_ack_received"]
        assert lane["established_sent"]
        assert not lane["play_sync_active"]
        assert [lane] == owner.wrapped_connects
        assert [
            build_rb_udp_control_packet(
                word4=0x0F000007,
                word8=0x01000000,
                local_id=1,
                remote_id=1,
                status_word=owner.CONTROL_ESTABLISHED_STATUS,
                nonce=0x1234,
            )
        ] == owner.sent

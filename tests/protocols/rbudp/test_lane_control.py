from types import SimpleNamespace

from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.lanes.control import RbUdpLaneControl
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


def _lane() -> RbUdpLane:
    return {
        "src_id": 0x4000006,
        "bootstrap_word8": 0x01000000,
        "peer_word4": 0x01000000,
        "peer_word8": 0x3D000022,
        "word4": 0x3D000022,
        "word8": 0x01000000,
        "local_id": 813,
        "remote_id": 84907,
        "nonce": 0,
    }


class _BufferedStream:
    def __init__(self, size: int) -> None:
        self.buffer = b"x" * size


class _Owner:
    def __init__(self, *, buffered: int = 0) -> None:
        self._peer_addr = ("127.0.0.1", 59318)
        self._receive_streams = SimpleNamespace(
            streams={(0x01000000, 0x3D000022): _BufferedStream(buffered)}
        )
        self.sent: list[bytes] = []
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.lane_control = RbUdpLaneControl(self)

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        return 0x1234

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _send_udp(self, packet: bytes) -> None:
        self.sent.append(packet)


class RbUdpLaneControlTests:
    def test_native_status_word_advertises_remaining_receive_window(
        self,
    ) -> None:
        owner = _Owner(buffered=0x10)

        status = owner.lane_control.native_control_status_word(
            _lane(), 0xFFFF0900
        )

        assert 0xFFF00900 == status

    def test_send_lane_control_can_ack_without_mutating_lane_state(
        self,
    ) -> None:
        owner = _Owner(buffered=0)
        lane = _lane()
        before = dict(lane)

        owner.lane_control.send_lane_control(
            lane,
            status_word=0xFFFF0900,
            local_id=1,
            remote_id=2,
            word4=0x01000000,
            word8=0x3D000022,
            log_label="ack",
            update_lane=False,
            advertise_window=True,
        )

        expected = build_rb_udp_control_packet(
            word4=0x01000000,
            word8=0x3D000022,
            local_id=1,
            remote_id=2,
            status_word=0xFFFF0900,
            nonce=0x1234,
        )
        assert before == lane
        assert [expected] == owner.sent
        assert "ack" == owner.debug[0][0]

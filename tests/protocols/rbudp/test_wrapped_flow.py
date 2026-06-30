import threading
from types import SimpleNamespace

from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.core.models import (
    ParsedKcpConnectResponse,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.kcp.link_packets import (
    build_kcp_connect_packet,
    build_rb_data_ack_packet,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.wrapped.frame_handler import (
    RbUdpWrappedFrameHandler,
)
from quii_helper.protocols.rbudp.wrapped.lanes import (
    RbUdpWrappedLaneState,
)
from quii_helper.protocols.rbudp.wrapped.packets import (
    build_rb_udp_wrapped_packet,
)
from quii_helper.protocols.rbudp.wrapped.sender import (
    RbUdpWrappedSender,
)


def _lane() -> RbUdpLane:
    return {
        "src_id": 0x04000006,
        "word4": 0x3D000022,
        "word8": 0x01000000,
        "local_id": 77,
        "remote_id": 165,
        "nonce": 0x1234,
        "connect_sent": False,
        "setup_probe_sent": False,
        "peer_logic_id": 77,
        "progress_sent": False,
        "quii_setup_acked": False,
    }


class _SenderOwner(RbUdpProtocolConstants):
    def __init__(self) -> None:
        self.config = SimpleNamespace(logical_channel=2, logical_conn_type=1)
        self._peer_addr = ("127.0.0.1", 59318)
        self.lane = _lane()
        self._lane_states = [self.lane]
        self.dest_id = None
        self.dest_ids: dict[int, int] = {}
        self.sent: list[bytes] = []
        self.debug: list[tuple[str, dict[str, object]]] = []

    def _active_lane(self) -> RbUdpLane:
        return self.lane

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        return 0xCAFE

    def _send_udp(self, packet: bytes) -> None:
        self.sent.append(packet)

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))


class _LaneOwner(RbUdpProtocolConstants):
    def __init__(self) -> None:
        self._lane_states = [_lane()]
        self.sent_control: list[tuple[RbUdpLane, dict[str, object]]] = []

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
    ) -> None:
        self.sent_control.append(
            (
                lane,
                {
                    "status_word": status_word,
                    "local_id": local_id,
                    "remote_id": remote_id,
                    "log_label": log_label,
                },
            )
        )


class _FrameOwner:
    def __init__(self) -> None:
        self._connected = threading.Event()
        self._quii_setup_acked = threading.Event()
        self._wrapped_debug_seen: set[str] = set()
        self.lane = _lane()
        self.dest_id = None
        self.dest_ids: dict[int, int] = {}
        self.local_id = 0
        self.remote_id = 0
        self.src_id = 0
        self.word4 = 0
        self.word8 = 0
        self.sent_setup: list[tuple[RbUdpLane, int, int]] = []
        self.debug: list[tuple[str, dict[str, object]]] = []

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _lane_for_src_id(self, src_id: int) -> RbUdpLane | None:
        if src_id == int(self.lane["src_id"]):
            return self.lane
        return None

    def _send_wrapped_setup_probe(
        self, lane: RbUdpLane, *, connect_id: int, dest_id: int
    ) -> None:
        self.sent_setup.append((lane, connect_id, dest_id))
        lane["setup_probe_sent"] = True


class RbUdpWrappedFlowTests:
    def test_wrapped_lane_component_refreshes_lane_once(self) -> None:
        owner = _LaneOwner()
        lane = owner._lane_states[0]
        lane["local_id"] = 0
        lane["remote_id"] = 0
        wrapped = ParsedRbUdpWrappedPacket(
            marker=0xFFABEFC1,
            word4=0x01000000,
            word8=0x3D000022,
            local_id=1,
            remote_id=77,
            status_word=owner.WRAPPED_STATUS,
            rand16=0,
            packet_len16=0,
            inner_total_length=0x10,
            tag8=owner.CONNECT_TAG,
            inner_packet=b"",
        )
        state = RbUdpWrappedLaneState(owner)

        assert lane is state.lane_for_wrapped(wrapped)
        state.refresh_lane_from_wrapped(lane, wrapped)
        state.refresh_lane_from_wrapped(lane, wrapped)

        assert 1 == lane["local_id"]
        assert 77 == lane["remote_id"]
        assert True is lane["progress_sent"]
        assert 1 == len(owner.sent_control)

    def test_wrapped_sender_component_matches_adapter_packet(self) -> None:
        owner = _SenderOwner()
        inner = build_rb_data_ack_packet(
            payload_length=0,
            seq=9,
            src_id=0x04000006,
            dest_id=0x12340000,
        )
        sender = RbUdpWrappedSender(owner)

        sender.send_wrapped(inner, tag8=owner.DATA_TAG)

        expected = build_rb_udp_wrapped_packet(
            inner,
            word4=0x3D000022,
            word8=0x01000000,
            local_id=77,
            remote_id=165,
            status_word=owner.WRAPPED_STATUS,
            nonce=0xCAFE,
            tag8=owner.DATA_TAG,
        )
        assert [expected] == owner.sent
        assert 77 + len(inner) == owner.lane["local_id"]

    def test_wrapped_frame_handler_component_sets_active_destination(
        self,
    ) -> None:
        owner = _FrameOwner()
        connect = ParsedKcpConnectResponse(
            packet_length=0x4C,
            packet_type_flag=1,
            command=0x120101,
            result_code=256,
            payload_length=36,
            connect_id=0x04000006,
            dest_id=0x45210000,
        )
        handler = RbUdpWrappedFrameHandler(owner)

        handler.handle_connect_frame(connect)

        assert {0x04000006: 0x45210000} == owner.dest_ids
        assert 0x04000006 == owner.src_id
        assert 0x45210000 == owner.dest_id
        assert 0x3D000022 == owner.word4
        assert 0x01000000 == owner.word8
        assert [(owner.lane, 0x04000006, 0x45210000)] == owner.sent_setup
        assert True is owner._connected.is_set()

    def test_send_wrapped_matches_native_packet_and_advances_local_id(
        self,
    ) -> None:
        owner = _SenderOwner()
        inner = build_rb_data_ack_packet(
            payload_length=0,
            seq=9,
            src_id=0x04000006,
            dest_id=0x12340000,
        )

        RbUdpWrappedSender(owner).send_wrapped(inner, tag8=owner.DATA_TAG)

        expected = build_rb_udp_wrapped_packet(
            inner,
            word4=0x3D000022,
            word8=0x01000000,
            local_id=77,
            remote_id=165,
            status_word=owner.WRAPPED_STATUS,
            nonce=0xCAFE,
            tag8=owner.DATA_TAG,
        )
        assert [expected] == owner.sent
        assert 77 + len(inner) == owner.lane["local_id"]

    def test_send_wrapped_connect_uses_configured_channel_bits(self) -> None:
        owner = _SenderOwner()

        RbUdpWrappedSender(owner).send_wrapped_connect(owner.lane)

        expected_inner = build_kcp_connect_packet(
            src_id=0x04000006,
            channel=2,
            conn_type=1,
        )
        expected = build_rb_udp_wrapped_packet(
            expected_inner,
            word4=0x3D000022,
            word8=0x01000000,
            local_id=77,
            remote_id=165,
            status_word=owner.WRAPPED_STATUS,
            nonce=0xCAFE,
            tag8=owner.CONNECT_TAG,
        )
        assert [expected] == owner.sent
        assert True is owner.lane["connect_sent"]

    def test_refresh_lane_from_connect_wrapped_sends_progress_once(
        self,
    ) -> None:
        owner = _LaneOwner()
        lane = owner._lane_states[0]
        lane["local_id"] = 0
        lane["remote_id"] = 0
        wrapped = ParsedRbUdpWrappedPacket(
            marker=0xFFABEFC1,
            word4=0x01000000,
            word8=0x3D000022,
            local_id=1,
            remote_id=77,
            status_word=owner.WRAPPED_STATUS,
            rand16=0,
            packet_len16=0,
            inner_total_length=0x10,
            tag8=owner.CONNECT_TAG,
            inner_packet=b"",
        )

        state = RbUdpWrappedLaneState(owner)
        state.refresh_lane_from_wrapped(lane, wrapped)
        state.refresh_lane_from_wrapped(lane, wrapped)

        assert 1 == lane["local_id"]
        assert 77 == lane["remote_id"]
        assert True is lane["progress_sent"]
        assert 1 == len(owner.sent_control)
        assert (
            owner.CONTROL_PROGRESS_STATUS
            == owner.sent_control[0][1]["status_word"]
        )
        assert "send_control_progress" == owner.sent_control[0][1]["log_label"]

    def test_connect_response_sets_active_destination_and_sends_setup_probe(
        self,
    ) -> None:
        owner = _FrameOwner()
        connect = ParsedKcpConnectResponse(
            packet_length=0x4C,
            packet_type_flag=1,
            command=0x120101,
            result_code=256,
            payload_length=36,
            connect_id=0x04000006,
            dest_id=0x45210000,
        )

        RbUdpWrappedFrameHandler(owner).handle_connect_frame(connect)

        assert {0x04000006: 0x45210000} == owner.dest_ids
        assert 0x04000006 == owner.src_id
        assert 0x45210000 == owner.dest_id
        assert 0x3D000022 == owner.word4
        assert 0x01000000 == owner.word8
        assert 77 == owner.local_id
        assert 165 == owner.remote_id
        assert [(owner.lane, 0x04000006, 0x45210000)] == owner.sent_setup
        assert True is owner._connected.is_set()

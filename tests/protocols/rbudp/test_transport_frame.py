from quii_helper.protocols.p2p.transport.packets import (
    build_p2p_transport_packet,
    parse_p2p_transport_frame,
)
from quii_helper.protocols.rbudp.transport.frame_handler import (
    RbUdpTransportFrameHandler,
)


class _UdpSocket:
    def __init__(self, port: int = 61500) -> None:
        self.port = port

    def getsockname(self) -> tuple[str, int]:
        return ("0.0.0.0", self.port)


class _TransportFrameOwner:
    def __init__(self) -> None:
        self._bootstrap_sent_to: tuple[str, int] | None = None
        self._late_bootstrap_pending = 0
        self._late_post_bootstrap_prime = False
        self._p2p_session_flag = "session-flag"
        self._peer_addr = ("192.168.1.176", 59318)
        self._transport_frames_seen = 0
        self._transport_peer_addr = self._peer_addr
        self._udp_sock = _UdpSocket()
        self.local_id = 1
        self.remote_id = 77
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.primed: list[int | None] = []
        self.bootstrap_count = 0
        self.sent_transport: list[tuple[bytes, tuple[str, int] | None]] = []

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        self.primed.append(seq_base)

    def _send_control_bootstrap(self) -> None:
        self.bootstrap_count += 1

    def _send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None:
        self.sent_transport.append((packet, peer_addr))


class RbUdpTransportFrameTests:
    def test_component_acks_rebind_without_replacing_private_peer(
        self,
    ) -> None:
        owner = _TransportFrameOwner()
        packet = build_p2p_transport_packet(
            session_flag="session-flag",
            seq=7,
            local_udp_port=6000,
            remote_ip="8.8.8.8",
            remote_port=43210,
            tail_code=200,
            packet_type_flag=0,
            rand16=1,
        )

        consumed = RbUdpTransportFrameHandler(owner).consume_transport_frame(
            packet
        )

        assert consumed
        assert owner._transport_frames_seen == 1
        assert owner._transport_peer_addr == ("8.8.8.8", 43210)
        assert owner._peer_addr == ("192.168.1.176", 59318)
        assert len(owner.sent_transport) == 1
        ack_packet, ack_peer = owner.sent_transport[0]
        ack_frame = parse_p2p_transport_frame(ack_packet)
        assert ack_peer == ("8.8.8.8", 43210)
        assert ack_frame.is_response
        assert ack_frame.seq == 7
        assert ack_frame.remote_ip == "8.8.8.8"
        assert ack_frame.remote_port == 43210

    def test_component_runs_deferred_bootstrap_after_late_frame(self) -> None:
        owner = _TransportFrameOwner()
        owner._late_bootstrap_pending = 1
        owner._late_post_bootstrap_prime = True
        packet = build_p2p_transport_packet(
            session_flag="session-flag",
            seq=8,
            local_udp_port=6000,
            remote_ip="",
            remote_port=0,
            tail_code=102,
            packet_type_flag=0,
            rand16=2,
        )

        consumed = RbUdpTransportFrameHandler(owner).consume_transport_frame(
            packet
        )

        assert consumed
        assert owner._transport_frames_seen == 1
        assert owner.bootstrap_count == 1
        assert owner.primed == [None]
        assert not owner._late_post_bootstrap_prime
        assert owner.sent_transport == []

    def test_component_ignores_transport_frame_for_other_session(self) -> None:
        owner = _TransportFrameOwner()
        packet = build_p2p_transport_packet(
            session_flag="other-session",
            seq=9,
            local_udp_port=6000,
            remote_ip="8.8.4.4",
            remote_port=12345,
            tail_code=200,
            packet_type_flag=0,
            rand16=3,
        )

        consumed = RbUdpTransportFrameHandler(owner).consume_transport_frame(
            packet
        )

        assert not consumed
        assert owner._transport_frames_seen == 0
        assert owner.sent_transport == []
        assert owner.debug[0][0] == "transport_session_mismatch"

from typing import Protocol

from quii_helper.network import is_private_ipv4
from quii_helper.protocols.p2p.models import ParsedP2PTransportFrame
from quii_helper.protocols.p2p.transport.packets import (
    build_p2p_transport_ack,
    parse_p2p_transport_frame,
)


class _UdpSocketLike(Protocol):
    def getsockname(self) -> tuple[str, int]: ...


class RbUdpTransportFrameOwner(Protocol):
    _bootstrap_sent_to: tuple[str, int] | None
    _late_bootstrap_pending: int
    _late_post_bootstrap_prime: bool
    _p2p_session_flag: str
    _peer_addr: tuple[str, int]
    _transport_frames_seen: int
    _transport_peer_addr: tuple[str, int]
    _udp_sock: _UdpSocketLike
    local_id: int
    remote_id: int

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None: ...

    def _send_control_bootstrap(self) -> None: ...

    def _send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None: ...


class RbUdpTransportFrameHandler:
    """Consume P2P transport frames around an RBUDP tunnel."""

    def __init__(self, owner: RbUdpTransportFrameOwner) -> None:
        self._owner = owner

    def consume_transport_frame(self, data: bytes) -> bool:
        owner = self._owner
        try:
            frame = parse_p2p_transport_frame(data)
        except Exception as exc:
            if len(data) == 164:
                owner._dbg(
                    "transport_parse_fail",
                    error=repr(exc),
                    prefix=data[:32].hex(),
                )
            return False
        if frame.session_flag != owner._p2p_session_flag and not (
            owner._p2p_session_flag.startswith(frame.session_flag)
            or frame.session_flag.startswith(owner._p2p_session_flag)
        ):
            owner._dbg(
                "transport_session_mismatch",
                got=frame.session_flag,
                want=owner._p2p_session_flag,
                remote_ip=frame.remote_ip,
                remote_port=frame.remote_port,
                tail=frame.tail_code,
                packet_type=frame.packet_type_flag,
            )
            return False
        owner._dbg(
            "transport_frame",
            remote_ip=frame.remote_ip,
            remote_port=frame.remote_port,
            tail=frame.tail_code,
            packet_type=frame.packet_type_flag,
        )
        owner._transport_frames_seen += 1
        self.handle_late_bootstrap_progress()
        if frame.is_request and frame.remote_ip and frame.remote_port:
            self.ack_transport_rebind(frame)
        return True

    def handle_late_bootstrap_progress(self) -> None:
        owner = self._owner
        if owner._late_bootstrap_pending <= 0:
            return
        owner._late_bootstrap_pending -= 1
        if owner._late_bootstrap_pending != 0:
            return
        owner._send_control_bootstrap()
        if owner._late_post_bootstrap_prime:
            owner._prime_lan_transport()
            owner._late_post_bootstrap_prime = False

    def ack_transport_rebind(self, frame: ParsedP2PTransportFrame) -> None:
        owner = self._owner
        ack = build_p2p_transport_ack(
            frame, local_udp_port=owner._udp_sock.getsockname()[1]
        )
        new_peer = (frame.remote_ip, frame.remote_port)
        owner._transport_peer_addr = new_peer
        owner._send_transport_udp(ack, peer_addr=new_peer)
        current_peer_is_private = is_private_ipv4(owner._peer_addr[0])
        if current_peer_is_private:
            owner._dbg(
                "ignore_transport_peer_rebind",
                current_peer=owner._peer_addr,
                transport_peer=new_peer,
                transport_keepalive_peer=owner._transport_peer_addr,
            )
            return
        peer_changed = new_peer != owner._peer_addr
        owner._peer_addr = new_peer
        if (
            owner.local_id == 0
            and owner.remote_id == 0
            and (peer_changed or owner._bootstrap_sent_to != new_peer)
        ):
            owner._dbg("bootstrap_to_new_transport_peer", peer=new_peer)
            owner._send_control_bootstrap()

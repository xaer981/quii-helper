import random
import socket
import time
from typing import Protocol

from quii_helper.network import is_private_ipv4
from quii_helper.protocols.p2p.transport.packets import build_p2p_active_packet
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class _EventLike(Protocol):
    def is_set(self) -> bool: ...


class RbUdpKeepaliveOwner(Protocol):
    _bootstrap_sent_to: tuple[str, int] | None
    _lane_states: list[RbUdpLane]
    _p2p_session_flag: str
    _peer_addr: tuple[str, int]
    _stop: _EventLike
    _transport_peer_addr: tuple[str, int]
    _udp_sock: socket.socket | None

    def _send_control_bootstrap(self) -> None: ...

    def _send_control_established(self, lane: RbUdpLane) -> None: ...

    def _send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None: ...


class RbUdpKeepalive:
    """Run periodic RBUDP keepalive and handshake refresh packets."""

    def __init__(self, owner: RbUdpKeepaliveOwner) -> None:
        self._owner = owner

    def run_loop(self) -> None:
        time.sleep(1.0)
        owner = self._owner
        while not owner._stop.is_set():
            try:
                if owner._udp_sock is None:
                    return
                local_udp_port = owner._udp_sock.getsockname()[1]
                lan_same_peer = (
                    owner._peer_addr == owner._transport_peer_addr
                    and is_private_ipv4(owner._peer_addr[0])
                )
                if not lan_same_peer:
                    packet = build_p2p_active_packet(
                        session_flag=owner._p2p_session_flag,
                        seq=random.randrange(0x100000000),
                        local_udp_port=local_udp_port,
                        tail_code=3,
                    )
                    owner._send_transport_udp(packet)
                sent_established = False
                for lane in owner._lane_states:
                    if int(lane["local_id"]) and int(lane["remote_id"]):
                        sent_established = True
                        if not bool(lane["established_sent"]):
                            owner._send_control_established(lane)
                if (
                    not sent_established
                    and owner._bootstrap_sent_to != owner._peer_addr
                ):
                    owner._send_control_bootstrap()
            except Exception:
                if owner._stop.is_set():
                    return
                pass
            time.sleep(1.0)

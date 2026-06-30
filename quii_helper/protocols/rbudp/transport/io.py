import random
import socket
import threading
from typing import Protocol

from quii_helper.network import udp_target_tuple
from quii_helper.protocols.p2p.transport.packets import build_p2p_active_packet


class RbUdpTransportIOOwner(Protocol):
    _udp_sock: socket.socket | None
    _peer_addr: tuple[str, int]
    _transport_peer_addr: tuple[str, int]
    _p2p_session_flag: str
    _stop: threading.Event

    def _dbg(self, message: str, **kwargs: object) -> None: ...


class RbUdpTransportIO:
    """Send RBUDP packets over the configured logical and transport peers."""

    def __init__(self, owner: RbUdpTransportIOOwner) -> None:
        self._owner = owner

    @property
    def peer_addr(self) -> tuple[str, int]:
        return self._owner._peer_addr

    @property
    def transport_peer_addr(self) -> tuple[str, int]:
        return self._owner._transport_peer_addr

    def send_udp(self, packet: bytes) -> None:
        owner = self._owner
        if owner._udp_sock is None:
            if owner._stop.is_set():
                return
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        if owner._stop.is_set():
            return
        try:
            owner._udp_sock.sendto(
                packet,
                udp_target_tuple(
                    owner._udp_sock,
                    owner._peer_addr[0],
                    owner._peer_addr[1],
                ),
            )
        except OSError:
            if owner._stop.is_set():
                return
            raise

    def send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None:
        owner = self._owner
        if owner._udp_sock is None:
            if owner._stop.is_set():
                return
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        if owner._stop.is_set():
            return
        try:
            target = peer_addr or owner._transport_peer_addr
            owner._udp_sock.sendto(
                packet,
                udp_target_tuple(owner._udp_sock, target[0], target[1]),
            )
        except OSError:
            if owner._stop.is_set():
                return
            raise

    def prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        owner = self._owner
        if owner._udp_sock is None:
            if owner._stop.is_set():
                return
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        if owner._stop.is_set():
            return
        local_udp_port = owner._udp_sock.getsockname()[1]
        for idx, tail_code in enumerate((200, 102)):
            packet = build_p2p_active_packet(
                session_flag=owner._p2p_session_flag,
                seq=(
                    ((seq_base + idx) & 0xFFFFFFFF)
                    if seq_base is not None
                    else random.randrange(0x100000000)
                ),
                local_udp_port=local_udp_port,
                tail_code=tail_code,
            )
            owner._dbg(
                "prime_lan_transport",
                peer=owner._transport_peer_addr,
                tail=tail_code,
                seq=(
                    hex((seq_base + idx) & 0xFFFFFFFF)
                    if seq_base is not None
                    else "random"
                ),
            )
            self.send_transport_udp(
                packet, peer_addr=owner._transport_peer_addr
            )

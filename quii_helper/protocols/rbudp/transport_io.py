import random
import socket

from quii_helper.network import udp_target_tuple
from quii_helper.protocols.p2p.transport_packets import build_p2p_active_packet


class RbUdpTransportIOMixin:
    _udp_sock: socket.socket | None
    _peer_addr: tuple[str, int]
    _transport_peer_addr: tuple[str, int]
    _p2p_session_flag: str

    def _dbg(self, message: str, **kwargs) -> None:
        raise NotImplementedError

    @property
    def peer_addr(self) -> tuple[str, int]:
        return self._peer_addr

    @property
    def transport_peer_addr(self) -> tuple[str, int]:
        return self._transport_peer_addr

    def _send_udp(self, packet: bytes) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        self._udp_sock.sendto(
            packet,
            udp_target_tuple(
                self._udp_sock, self._peer_addr[0], self._peer_addr[1]
            ),
        )

    def _send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        target = peer_addr or self._transport_peer_addr
        self._udp_sock.sendto(
            packet, udp_target_tuple(self._udp_sock, target[0], target[1])
        )

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        local_udp_port = self._udp_sock.getsockname()[1]
        for idx, tail_code in enumerate((200, 102)):
            packet = build_p2p_active_packet(
                session_flag=self._p2p_session_flag,
                seq=(
                    ((seq_base + idx) & 0xFFFFFFFF)
                    if seq_base is not None
                    else random.randrange(0x100000000)
                ),
                local_udp_port=local_udp_port,
                tail_code=tail_code,
            )
            self._dbg(
                "prime_lan_transport",
                peer=self._transport_peer_addr,
                tail=tail_code,
                seq=(
                    hex((seq_base + idx) & 0xFFFFFFFF)
                    if seq_base is not None
                    else "random"
                ),
            )
            self._send_transport_udp(
                packet, peer_addr=self._transport_peer_addr
            )

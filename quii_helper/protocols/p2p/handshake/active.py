import random
import socket
import time

from quii_helper.network import udp_target_tuple
from quii_helper.protocols.p2p.models import ParsedP2PTransportFrame
from quii_helper.protocols.p2p.transport.packets import (
    build_p2p_active_packet,
    build_p2p_transport_ack,
    parse_p2p_transport_frame,
)


def run_p2p_active_handshake(
    *,
    sock: socket.socket,
    session_flag: str,
    timeout: float,
    rng: random.Random,
    peer_hint: tuple[str, int] | None = None,
) -> tuple[tuple[str, int], list[ParsedP2PTransportFrame]]:
    local_udp_port = sock.getsockname()[1]
    sock.settimeout(min(timeout, 0.5))
    seen_requests: list[ParsedP2PTransportFrame] = []
    peer: tuple[str, int] | None = None
    deadline = time.time() + timeout
    active_sent = False

    def send_active(peer_addr: tuple[str, int]) -> None:
        nonlocal active_sent
        for tail_code in (200, 102):
            active = build_p2p_active_packet(
                session_flag=session_flag,
                seq=rng.randrange(0x100000000),
                local_udp_port=local_udp_port,
                tail_code=tail_code,
            )
            sock.sendto(
                active, udp_target_tuple(sock, peer_addr[0], peer_addr[1])
            )
        active_sent = True

    while time.time() < deadline:
        if (
            not active_sent
            and peer_hint is not None
            and time.time() + 0.5 >= deadline
        ):
            send_active(peer_hint)
        try:
            data, _addr = sock.recvfrom(4096)
        except TimeoutError:
            if not active_sent and peer_hint is not None:
                send_active(peer_hint)
            continue
        try:
            frame = parse_p2p_transport_frame(data)
        except Exception:
            continue
        if frame.session_flag != session_flag:
            continue
        if frame.is_request and frame.remote_ip and frame.remote_port:
            seen_requests.append(frame)
            peer = (frame.remote_ip, frame.remote_port)
            ack = build_p2p_transport_ack(frame, local_udp_port=local_udp_port)
            sock.sendto(
                ack, udp_target_tuple(sock, frame.remote_ip, frame.remote_port)
            )
            if not active_sent:
                send_active(peer)
            if len(seen_requests) >= 2:
                break

    if peer is None and peer_hint is not None:
        peer = peer_hint
        if not active_sent:
            send_active(peer_hint)

    if peer is None:
        raise TimeoutError(
            "no inbound P2P transport request frames after probe"
        )

    return peer, seen_requests

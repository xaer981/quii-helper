import random
import socket

from quii_helper.config import AutonomousConfig
from quii_helper.network import is_private_ipv4
from quii_helper.protocols.p2p.active_handshake import run_p2p_active_handshake
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.p2p.peer_selection import (
    describe_logic_peer_selection,
    format_peer,
    format_probe_targets,
    select_preferred_logic_peer,
)
from quii_helper.protocols.p2p.udp_probe import run_udp_probe


def log_p2pconnect_response(response: P2PConnectResponse) -> None:
    print(
        "[P2PDiag] p2pconnect_response",
        {
            "response_local_ips": response.local_ips,
            "response_local_udp_port": response.local_udp_port,
            "public_peer": format_peer(
                (response.public_ip or "", int(response.public_udp_port or 0))
            ),
            "trans_peer": format_peer(
                (
                    response.utd_public_ip or "",
                    int(response.utd_public_udp_port or 0),
                )
            ),
            "probe_targets": format_probe_targets(response),
        },
    )


def probe_and_select_direct_peers(
    *,
    config: AutonomousConfig,
    udp_sock: socket.socket,
    response: P2PConnectResponse,
    request_session_id: int,
    session_flag: str,
    rng: random.Random,
) -> tuple[ParsedP2PTestResponse, tuple[str, int], tuple[str, int]]:
    test_response = run_udp_probe(
        sock=udp_sock,
        response=response,
        request_session_id=request_session_id,
        target_session_flag=session_flag,
        ust_test_address=config.ust_test_address,
        timeout=config.udp_timeout,
        rng=rng,
    )
    if config.log_peer_diagnostics:
        print(
            "[P2PDiag] udp_probe_selected",
            {
                "test_peer": f"{test_response.address}:{test_response.port}",
                "test_id": test_response.test_id,
                "status_code": test_response.status_code,
                "result_code": test_response.result_code,
            },
        )
    if is_private_ipv4(test_response.address):
        transport_peer_addr = (test_response.address, test_response.port)
        peer_addr = transport_peer_addr
        print(f"[P2PActive] skip for LAN peer {peer_addr}")
        if config.log_peer_diagnostics:
            print(
                "[P2PDiag] peer_selection",
                {
                    "selection_mode": "lan_direct_from_udp_probe",
                    "transport_peer": format_peer(transport_peer_addr),
                    "logic_peer": format_peer(peer_addr),
                },
            )
        return test_response, peer_addr, transport_peer_addr

    transport_peer_addr, _seen_requests = run_p2p_active_handshake(
        sock=udp_sock,
        session_flag=session_flag,
        timeout=config.udp_timeout,
        rng=rng,
        peer_hint=(test_response.address, test_response.port),
    )
    selection = describe_logic_peer_selection(response, transport_peer_addr)
    peer_addr = select_preferred_logic_peer(response, transport_peer_addr)
    if config.log_peer_diagnostics:
        print(
            "[P2PDiag] peer_selection",
            {
                "selection_mode": "transport_then_logic_select",
                "transport_peer": format_peer(transport_peer_addr),
                **selection,
            },
        )
    return test_response, peer_addr, transport_peer_addr

import ipaddress
from typing import Any

from quii_helper.protocols.p2p.models import P2PConnectResponse
from quii_helper.protocols.p2p.targets import iter_p2p_test_targets


def format_peer(peer: tuple[str, int] | None) -> str:
    if peer is None:
        return "None"
    return f"{peer[0]}:{peer[1]}"


def format_probe_targets(response: P2PConnectResponse) -> list[str]:
    items: list[str] = []
    for target in iter_p2p_test_targets(response, force_trans=0):
        items.append(
            f"{target.kind}:{target.host}:{target.port}:"
            f"mode={target.mode}:reliable={int(target.reliable_hint)}"
        )
    return items


def format_logic_peer_candidates(response: P2PConnectResponse) -> list[str]:
    items: list[str] = []
    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            items.append(f"{candidate}:{response.local_udp_port}")
    return items


def has_probe_targets(response: P2PConnectResponse) -> bool:
    return bool(format_probe_targets(response))


def select_preferred_logic_peer(
    response: P2PConnectResponse, fallback_peer: tuple[str, int]
) -> tuple[str, int]:
    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            return candidate, response.local_udp_port
    return fallback_peer


def describe_logic_peer_selection(
    response: P2PConnectResponse,
    fallback_peer: tuple[str, int],
) -> dict[str, Any]:
    candidates = format_logic_peer_candidates(response)
    selected = select_preferred_logic_peer(response, fallback_peer)
    return {
        "fallback_peer": format_peer(fallback_peer),
        "candidate_logic_peers": candidates,
        "selected_logic_peer": format_peer(selected),
        "selected_from_response_local_ip": bool(
            candidates and selected != fallback_peer
        ),
    }

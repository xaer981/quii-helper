from dataclasses import dataclass
from typing import Protocol

from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)


class LogicalSrcConfig(Protocol):
    logical_src_id_base: int
    logical_src_id_count: int


@dataclass(frozen=True)
class RbUdpTunnelEndpoints:
    """Resolved peer endpoints and session flag used by RBUDP transport."""

    peer_addr: tuple[str, int]
    transport_peer_addr: tuple[str, int]
    p2p_session_flag: str


def build_logical_src_ids(config: LogicalSrcConfig) -> list[int]:
    """Build native-style logical source ids for all configured lanes."""

    return [
        (config.logical_src_id_base + index) & 0xFFFFFFFF
        for index in range(max(1, int(config.logical_src_id_count)))
    ]


def resolve_tunnel_endpoints(
    *,
    response: P2PConnectResponse,
    test_response: ParsedP2PTestResponse,
    peer_addr: tuple[str, int] | None = None,
    transport_peer_addr: tuple[str, int] | None = None,
    p2p_session_flag: str | None = None,
) -> RbUdpTunnelEndpoints:
    """Resolve explicit endpoint overrides against P2P test response values."""

    default_addr = (test_response.address, test_response.port)
    return RbUdpTunnelEndpoints(
        peer_addr=peer_addr or default_addr,
        transport_peer_addr=transport_peer_addr or default_addr,
        p2p_session_flag=p2p_session_flag or response.session_flag or "",
    )


def initial_direct_data_stats() -> dict[str, int]:
    """Return the direct-data stats keys expected by capture summaries."""

    return {
        "acked": 0,
        "replayed": 0,
        "gaps": 0,
    }

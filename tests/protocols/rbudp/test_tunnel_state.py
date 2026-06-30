from types import SimpleNamespace

from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel.state import (
    build_logical_src_ids,
    initial_direct_data_stats,
    resolve_tunnel_endpoints,
)


class RbUdpTunnelStateTests:
    def test_build_logical_src_ids_uses_at_least_one_lane(self) -> None:
        config = SimpleNamespace(
            logical_src_id_base=0x04000006,
            logical_src_id_count=0,
        )

        assert [0x04000006] == build_logical_src_ids(config)

    def test_build_logical_src_ids_wraps_uint32_values(self) -> None:
        config = SimpleNamespace(
            logical_src_id_base=0xFFFFFFFF,
            logical_src_id_count=3,
        )

        assert [0xFFFFFFFF, 0, 1] == build_logical_src_ids(config)

    def test_resolve_tunnel_endpoints_uses_test_response_defaults(
        self,
    ) -> None:
        response = P2PConnectResponse(session_flag="session")
        test_response = ParsedP2PTestResponse(
            result_code=0,
            session_flag="test-session",
            address="192.168.1.10",
            port=59318,
            status_code=0,
            test_id=0,
        )

        endpoints = resolve_tunnel_endpoints(
            response=response,
            test_response=test_response,
        )

        assert ("192.168.1.10", 59318) == endpoints.peer_addr
        assert ("192.168.1.10", 59318) == endpoints.transport_peer_addr
        assert "session" == endpoints.p2p_session_flag

    def test_resolve_tunnel_endpoints_prefers_explicit_overrides(self) -> None:
        response = P2PConnectResponse(session_flag="session")
        test_response = ParsedP2PTestResponse(
            result_code=0,
            session_flag="test-session",
            address="192.168.1.10",
            port=59318,
            status_code=0,
            test_id=0,
        )

        endpoints = resolve_tunnel_endpoints(
            response=response,
            test_response=test_response,
            peer_addr=("10.0.0.1", 1000),
            transport_peer_addr=("10.0.0.2", 2000),
            p2p_session_flag="override",
        )

        assert ("10.0.0.1", 1000) == endpoints.peer_addr
        assert ("10.0.0.2", 2000) == endpoints.transport_peer_addr
        assert "override" == endpoints.p2p_session_flag

    def test_initial_direct_data_stats_contains_summary_keys(self) -> None:
        assert {
            "acked": 0,
            "replayed": 0,
            "gaps": 0,
        } == initial_direct_data_stats()

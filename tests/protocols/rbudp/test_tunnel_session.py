from quii_helper.config import AutonomousConfig
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel.session import RbUdpQuiiTunnel


class RbUdpTunnelSessionTests:
    def test_initializes_runtime_state_without_starting_network_threads(
        self,
    ) -> None:
        config = AutonomousConfig(
            device_id="device",
            cloud_account="account",
            cloud_password="password",
            logical_src_id_base=0x04000006,
            logical_src_id_count=2,
            connect_timeout=0.01,
        )
        response = P2PConnectResponse(session_flag="session")
        test_response = ParsedP2PTestResponse(
            result_code=0,
            session_flag="test-session",
            address="192.168.1.10",
            port=59318,
            status_code=0,
            test_id=0,
        )

        tunnel = RbUdpQuiiTunnel(
            config,
            response,
            test_response,
            request_session_id=123,
            peer_addr=("10.0.0.1", 1000),
            transport_peer_addr=("10.0.0.2", 2000),
            p2p_session_flag="override",
        )

        assert [0x04000006, 0x04000007] == tunnel.src_ids
        assert 0x04000006 == tunnel.src_id
        assert ("10.0.0.1", 1000) == tunnel.peer_addr
        assert ("10.0.0.2", 2000) == tunnel.transport_peer_addr
        assert "override" == tunnel._p2p_session_flag
        summary = tunnel.fragment_summary()
        assert 0 == summary["direct_data_acked"]
        assert 0 == summary["direct_data_replayed"]
        assert 0 == summary["direct_data_gaps"]

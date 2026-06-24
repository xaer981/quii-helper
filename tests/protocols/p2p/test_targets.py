import unittest

from quii_helper.protocols.p2p.models import P2PConnectResponse
from quii_helper.protocols.p2p.peers.targets import iter_p2p_test_targets


class P2PTestTargetTests(unittest.TestCase):
    def test_targets_prefer_lan_then_public_then_trans(self) -> None:
        response = P2PConnectResponse(
            nettype=0,
            public_ip="203.0.113.10",
            public_udp_port=10001,
            local_udp_port=20002,
            local_ips=["not-an-ip", "192.168.1.20", "192.168.1.21"],
            utd_public_ip="198.51.100.20",
            utd_public_udp_port=30003,
        )

        targets = iter_p2p_test_targets(response)

        self.assertEqual(["lan", "p2p", "trans"], [t.kind for t in targets])
        self.assertEqual(
            ("192.168.1.20", 20002, 0),
            (
                targets[0].host,
                targets[0].port,
                targets[0].mode,
            ),
        )
        self.assertTrue(targets[0].reliable_hint)

    def test_force_trans_suppresses_public_p2p_only(self) -> None:
        response = P2PConnectResponse(
            nettype=0,
            public_ip="203.0.113.10",
            public_udp_port=10001,
            utd_public_ip="198.51.100.20",
            utd_public_udp_port=30003,
        )

        targets = iter_p2p_test_targets(response, force_trans=1)

        self.assertEqual(["trans"], [t.kind for t in targets])

    def test_nettype_bits_suppress_public_and_trans_probes(self) -> None:
        response = P2PConnectResponse(
            nettype=0x3,
            public_ip="203.0.113.10",
            public_udp_port=10001,
            utd_public_ip="198.51.100.20",
            utd_public_udp_port=30003,
        )

        self.assertEqual([], iter_p2p_test_targets(response))


if __name__ == "__main__":
    unittest.main()

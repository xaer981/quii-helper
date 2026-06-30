from quii_helper.network.state import (
    append_unique_non_loopback_ipv4,
    collect_non_loopback_ipv4s,
    local_ip_result,
    non_loopback_ipv4,
    valid_public_ip_response,
)


class NetworkStateTests:
    def test_non_loopback_ipv4_preserves_loopback_filter(self) -> None:
        assert "" == non_loopback_ipv4(None)
        assert "" == non_loopback_ipv4("")
        assert "" == non_loopback_ipv4("127.0.0.1")
        assert "192.168.1.10" == non_loopback_ipv4("192.168.1.10")

    def test_append_unique_non_loopback_ipv4_preserves_order(self) -> None:
        values = ["192.168.1.10"]

        append_unique_non_loopback_ipv4(values, "127.0.0.1")
        append_unique_non_loopback_ipv4(values, "192.168.1.10")
        append_unique_non_loopback_ipv4(values, "10.0.0.5")

        assert ["192.168.1.10", "10.0.0.5"] == values

    def test_collect_non_loopback_ipv4s_matches_getaddrinfo_shape(
        self,
    ) -> None:
        rows = [
            (2, 1, 6, "", ("127.0.0.1", 0)),
            (2, 1, 6, "", ("192.168.1.10", 0)),
            (2, 2, 17, "", ("192.168.1.10", 0)),
            (2, 1, 6, "", ("10.0.0.5", 0)),
        ]

        assert ["192.168.1.10", "10.0.0.5"] == (
            collect_non_loopback_ipv4s(rows)
        )

    def test_local_ip_result_prefers_primary_then_discovered_then_loopback(
        self,
    ) -> None:
        assert ["192.168.1.20"] == (
            local_ip_result(
                primary_ip="192.168.1.20",
                discovered=["10.0.0.5"],
            )
        )
        assert ["10.0.0.5"] == (
            local_ip_result(primary_ip=None, discovered=["10.0.0.5"])
        )
        assert ["127.0.0.1"] == (
            local_ip_result(primary_ip=None, discovered=[])
        )

    def test_valid_public_ip_response_matches_inet_aton_validation(
        self,
    ) -> None:
        assert "203.0.113.10" == (valid_public_ip_response(b"203.0.113.10\n"))
        assert "" == valid_public_ip_response(b"not-an-ip")

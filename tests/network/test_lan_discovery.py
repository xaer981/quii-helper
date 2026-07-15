from quii_helper.network import (
    HttpProbeResult,
    candidate_hosts,
    discover_lan_devices,
    is_qualvision_server_header,
    parse_http_probe_response,
    probe_lan_device,
)


class LanDiscoveryTests:
    def test_candidate_hosts_builds_subnet_hosts_without_local_ip(
        self,
    ) -> None:
        assert ["192.168.1.9"] == (
            candidate_hosts(["192.168.1.10"], subnet_prefix=30)
        )

    def test_candidate_hosts_skips_invalid_and_loopback_ips(self) -> None:
        assert [] == (
            candidate_hosts(
                ["bad", "127.0.0.1", "::1"],
                subnet_prefix=30,
            )
        )

    def test_parse_http_probe_response_extracts_server_header(self) -> None:
        result = parse_http_probe_response(
            b"HTTP/1.1 200 OK\r\n"
            b"Date: now\r\n"
            b"Server: Qualvision -HTTPServer\r\n\r\n"
        )

        assert "HTTP/1.1 200 OK" == result.status_line
        assert "Qualvision -HTTPServer" == result.server_header
        assert is_qualvision_server_header(result.server_header)

    def test_probe_lan_device_filters_non_qualvision_by_default(self) -> None:
        candidate = probe_lan_device(
            "192.168.1.20",
            http_probe=lambda host, port, timeout: HttpProbeResult(
                status_line="HTTP/1.1 200 OK",
                server_header="generic",
            ),
            port_probe=lambda host, port, timeout: True,
        )

        assert candidate is None

    def test_probe_lan_device_returns_qualvision_candidate(self) -> None:
        candidate = probe_lan_device(
            "192.168.1.20",
            http_probe=lambda host, port, timeout: HttpProbeResult(
                status_line="HTTP/1.1 200 OK",
                server_header="Qualvision -HTTPServer",
            ),
            port_probe=lambda host, port, timeout: True,
        )

        assert candidate is not None
        assert "192.168.1.20" == candidate.host
        assert candidate.is_qualvision_http
        assert candidate.stream_port_open

    def test_discover_lan_devices_scans_explicit_hosts(self) -> None:
        http_by_host = {
            "192.168.1.20": HttpProbeResult(
                status_line="HTTP/1.1 200 OK",
                server_header="Qualvision -HTTPServer",
            ),
            "192.168.1.21": HttpProbeResult(
                status_line="HTTP/1.1 200 OK",
                server_header="generic",
            ),
        }

        candidates = discover_lan_devices(
            hosts=["192.168.1.21", "192.168.1.20"],
            http_probe=lambda host, port, timeout: http_by_host.get(
                host,
                HttpProbeResult(),
            ),
            port_probe=lambda host, port, timeout: host == "192.168.1.20",
        )

        assert ["192.168.1.20"] == [candidate.host for candidate in candidates]

"""Local LAN discovery for Qualvision-compatible devices."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

DEFAULT_HTTP_PORT = 80
DEFAULT_STREAM_PORT = 34567
DEFAULT_DISCOVERY_TIMEOUT = 0.3
DEFAULT_SCAN_PREFIX = 24
QUALVISION_SERVER_MARKER = "qualvision"


@dataclass(frozen=True)
class HttpProbeResult:
    """HTTP probe result used by the LAN discovery scanner."""

    status_line: str = ""
    server_header: str = ""


@dataclass(frozen=True)
class LanDeviceCandidate:
    """One local network device candidate.

    Attributes:
        host: Candidate IPv4 address or hostname.
        http_port: HTTP port that responded to the probe.
        stream_port: Native media/control TCP port checked by the scanner.
        server_header: HTTP `Server` header returned by `GET /`.
        http_status_line: First HTTP response line returned by `GET /`.
        stream_port_open: Whether the native TCP port accepted a connection.
    """

    host: str
    http_port: int = DEFAULT_HTTP_PORT
    stream_port: int = DEFAULT_STREAM_PORT
    server_header: str = ""
    http_status_line: str = ""
    stream_port_open: bool = False

    @property
    def is_qualvision_http(self) -> bool:
        """Whether the HTTP server header matches Qualvision devices."""

        return is_qualvision_server_header(self.server_header)


HttpProbe = Callable[[str, int, float], HttpProbeResult]
PortProbe = Callable[[str, int, float], bool]


def discover_lan_devices(
    *,
    local_ips: Sequence[str] = (),
    hosts: Sequence[str] | None = None,
    subnet_prefix: int = DEFAULT_SCAN_PREFIX,
    http_port: int = DEFAULT_HTTP_PORT,
    stream_port: int = DEFAULT_STREAM_PORT,
    timeout: float = DEFAULT_DISCOVERY_TIMEOUT,
    max_workers: int = 64,
    require_qualvision: bool = True,
    http_probe: HttpProbe | None = None,
    port_probe: PortProbe | None = None,
) -> list[LanDeviceCandidate]:
    """Scan local hosts for Qualvision-compatible camera candidates.

    The scanner is intentionally read-only: it sends `GET /` to read the HTTP
    `Server` header and opens a short TCP connection to the native stream port.
    It does not send credentials and does not call `/tdkcgi`.
    """

    scan_hosts = (
        list(hosts)
        if hosts is not None
        else candidate_hosts(
            local_ips,
            subnet_prefix=subnet_prefix,
        )
    )
    if not scan_hosts:
        return []

    resolved_http_probe = http_probe or probe_http_server
    resolved_port_probe = port_probe or probe_tcp_port
    workers = max(1, min(max_workers, len(scan_hosts)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                probe_lan_device,
                host,
                http_port=http_port,
                stream_port=stream_port,
                timeout=timeout,
                require_qualvision=require_qualvision,
                http_probe=resolved_http_probe,
                port_probe=resolved_port_probe,
            )
            for host in scan_hosts
        ]
        candidates = [
            candidate
            for future in as_completed(futures)
            if (candidate := future.result()) is not None
        ]
    return sorted(
        candidates, key=lambda candidate: _host_sort_key(candidate.host)
    )


def candidate_hosts(
    local_ips: Sequence[str],
    *,
    subnet_prefix: int = DEFAULT_SCAN_PREFIX,
) -> list[str]:
    """Build unique scan candidates from local IPv4 addresses."""

    hosts: list[str] = []
    for local_ip in local_ips:
        try:
            address = ipaddress.ip_address(local_ip)
        except ValueError:
            continue
        if not isinstance(address, ipaddress.IPv4Address):
            continue
        if address.is_loopback or address.is_unspecified:
            continue
        network = ipaddress.ip_network(
            f"{address}/{subnet_prefix}",
            strict=False,
        )
        for host in network.hosts():
            candidate = str(host)
            if candidate != str(address) and candidate not in hosts:
                hosts.append(candidate)
    return hosts


def probe_lan_device(
    host: str,
    *,
    http_port: int = DEFAULT_HTTP_PORT,
    stream_port: int = DEFAULT_STREAM_PORT,
    timeout: float = DEFAULT_DISCOVERY_TIMEOUT,
    require_qualvision: bool = True,
    http_probe: HttpProbe | None = None,
    port_probe: PortProbe | None = None,
) -> LanDeviceCandidate | None:
    """Probe one host and return it when it matches discovery criteria."""

    http_result = (http_probe or probe_http_server)(host, http_port, timeout)
    stream_port_open = (port_probe or probe_tcp_port)(
        host,
        stream_port,
        timeout,
    )
    if not http_result.server_header and not stream_port_open:
        return None
    is_qualvision = is_qualvision_server_header(http_result.server_header)
    if require_qualvision and not is_qualvision:
        return None
    return LanDeviceCandidate(
        host=host,
        http_port=http_port,
        stream_port=stream_port,
        server_header=http_result.server_header,
        http_status_line=http_result.status_line,
        stream_port_open=stream_port_open,
    )


def probe_http_server(
    host: str,
    port: int = DEFAULT_HTTP_PORT,
    timeout: float = DEFAULT_DISCOVERY_TIMEOUT,
) -> HttpProbeResult:
    """Return the HTTP status line and `Server` header for `GET /`."""

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            request = (
                f"GET / HTTP/1.1\r\nHost: {host}\r\n"
                "Connection: close\r\n\r\n"
            )
            sock.sendall(request.encode("ascii"))
            return parse_http_probe_response(sock.recv(4096))
    except OSError:
        return HttpProbeResult()


def probe_tcp_port(
    host: str,
    port: int = DEFAULT_STREAM_PORT,
    timeout: float = DEFAULT_DISCOVERY_TIMEOUT,
) -> bool:
    """Return whether a TCP port accepts a short connection."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_http_probe_response(data: bytes) -> HttpProbeResult:
    """Parse a minimal HTTP response into `HttpProbeResult`."""

    text = data.decode("iso-8859-1", errors="replace")
    lines = text.replace("\r\n", "\n").split("\n")
    status_line = lines[0].strip() if lines else ""
    server_header = ""
    for line in lines[1:]:
        if not line.strip():
            break
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == "server":
            server_header = value.strip()
            break
    return HttpProbeResult(
        status_line=status_line,
        server_header=server_header,
    )


def is_qualvision_server_header(value: str) -> bool:
    """Return whether an HTTP `Server` header looks like Qualvision."""

    return QUALVISION_SERVER_MARKER in value.lower()


def _host_sort_key(host: str) -> tuple[int, int | str]:
    try:
        return (0, int(ipaddress.ip_address(host)))
    except ValueError:
        return (1, host)


__all__ = [
    "DEFAULT_DISCOVERY_TIMEOUT",
    "DEFAULT_HTTP_PORT",
    "DEFAULT_SCAN_PREFIX",
    "DEFAULT_STREAM_PORT",
    "HttpProbe",
    "HttpProbeResult",
    "LanDeviceCandidate",
    "PortProbe",
    "QUALVISION_SERVER_MARKER",
    "candidate_hosts",
    "discover_lan_devices",
    "is_qualvision_server_header",
    "parse_http_probe_response",
    "probe_http_server",
    "probe_lan_device",
    "probe_tcp_port",
]

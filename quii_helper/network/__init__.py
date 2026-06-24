import ipaddress
import socket
import urllib.request

from quii_helper.network.state import (
    collect_non_loopback_ipv4s,
    local_ip_result,
    non_loopback_ipv4,
    valid_public_ip_response,
)

DEFAULT_UDP_RECEIVE_BUFFER_SIZE = 4 * 1024 * 1024


def discover_local_ips() -> list[str]:
    """
    Report only the primary routed IPv4 address when possible.

    The Android app appears to advertise a single LAN/Wi-Fi address to UST.
    Sending every host-side adapter (VPN, WSL, Hyper-V, etc.) makes the peer
    choose the wrong local path much more often.
    """
    primary_ip: str | None = None
    discovered: list[str] = []

    probe: socket.socket | None = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        primary_ip = non_loopback_ipv4(ip) or None
    except OSError:
        pass
    finally:
        if probe is not None:
            try:
                probe.close()
            except Exception:
                pass

    try:
        host_name = socket.gethostname()
        discovered = collect_non_loopback_ipv4s(
            socket.getaddrinfo(host_name, None, socket.AF_INET)
        )
    except OSError:
        pass

    return local_ip_result(primary_ip=primary_ip, discovered=discovered)


def discover_public_ip(timeout: float = 5.0) -> str:
    candidates = (
        "https://api.ipify.org",
        "https://ipv4.icanhazip.com",
    )
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                value = valid_public_ip_response(resp.read())
            if value:
                return value
        except Exception:
            continue
    return "0.0.0.0"


def make_dualstack_udp_socket(
    receive_buffer_size: int = DEFAULT_UDP_RECEIVE_BUFFER_SIZE,
) -> socket.socket:
    def configure_socket(sock: socket.socket) -> socket.socket:
        try:
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer_size
            )
        except OSError:
            pass
        return sock

    try:
        sock = configure_socket(
            socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        )
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        sock.bind(("::", 0))
        return sock
    except OSError:
        sock = configure_socket(
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )
        sock.bind(("0.0.0.0", 0))
        return sock


def udp_target_tuple(sock: socket.socket, host: str, port: int):
    if sock.family == socket.AF_INET6:
        return (f"::ffff:{host}", port, 0, 0)
    return (host, port)


def is_private_ipv4(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private


def to_signed_i32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        return value - 0x100000000
    return value

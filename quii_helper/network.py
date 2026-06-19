import ipaddress
import socket
import urllib.request


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
        if ip and not ip.startswith("127."):
            primary_ip = ip
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
        for _family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(
            host_name, None, socket.AF_INET
        ):
            ip = sockaddr[0]
            if not ip or ip.startswith("127."):
                continue
            if ip not in discovered:
                discovered.append(ip)
    except OSError:
        pass

    if primary_ip:
        return [primary_ip]

    return discovered or ["127.0.0.1"]


def discover_public_ip(timeout: float = 5.0) -> str:
    candidates = (
        "https://api.ipify.org",
        "https://ipv4.icanhazip.com",
    )
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                value = resp.read().decode("utf-8", errors="ignore").strip()
            socket.inet_aton(value)
            return value
        except Exception:
            continue
    return "0.0.0.0"


def make_dualstack_udp_socket() -> socket.socket:
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        sock.bind(("::", 0))
        return sock
    except OSError:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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

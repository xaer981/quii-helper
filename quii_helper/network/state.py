import socket
from collections.abc import Iterable, Sequence
from typing import Any


def non_loopback_ipv4(value: str | None) -> str:
    if value and not value.startswith("127."):
        return value
    return ""


def append_unique_non_loopback_ipv4(
    values: list[str],
    value: str | None,
) -> None:
    ip = non_loopback_ipv4(value)
    if ip and ip not in values:
        values.append(ip)


def local_ip_result(
    *,
    primary_ip: str | None,
    discovered: Sequence[str],
) -> list[str]:
    primary = non_loopback_ipv4(primary_ip)
    if primary:
        return [primary]
    return list(discovered) or ["127.0.0.1"]


def collect_non_loopback_ipv4s(
    addrinfo_rows: Iterable[tuple[Any, Any, Any, Any, Any]],
) -> list[str]:
    values: list[str] = []
    for row in addrinfo_rows:
        sockaddr = row[4]
        candidate = sockaddr[0] if isinstance(sockaddr, tuple) else None
        append_unique_non_loopback_ipv4(
            values, candidate if isinstance(candidate, str) else None
        )
    return values


def valid_public_ip_response(value: bytes) -> str:
    candidate = value.decode("utf-8", errors="ignore").strip()
    try:
        socket.inet_aton(candidate)
    except OSError:
        return ""
    return candidate

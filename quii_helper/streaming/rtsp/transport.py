def interleaved_channel(transport: str) -> int | None:
    marker = "interleaved="
    lower = transport.lower()
    start = lower.find(marker)
    if start < 0:
        return 0
    value = transport[start + len(marker) :].split(";", 1)[0]
    try:
        parts = value.split("-", 1)
        first = int(parts[0])
        second = int(parts[1]) if len(parts) == 2 else first + 1
    except ValueError:
        return None
    return first if 0 <= first < 255 and second == first + 1 else None


def client_ports(transport: str) -> tuple[int, int] | None:
    marker = "client_port="
    lower = transport.lower()
    start = lower.find(marker)
    if start < 0:
        return None
    value = transport[start + len(marker) :].split(";", 1)[0]
    parts = value.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        ports = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return ports if all(0 < port <= 65535 for port in ports) else None

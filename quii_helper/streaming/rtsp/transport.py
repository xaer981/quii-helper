def interleaved_channel(transport: str) -> int:
    marker = "interleaved="
    lower = transport.lower()
    start = lower.find(marker)
    if start < 0:
        return 0
    value = transport[start + len(marker) :].split(";", 1)[0]
    first = value.split("-", 1)[0]
    try:
        return int(first)
    except ValueError:
        return 0


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
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None

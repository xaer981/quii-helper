import ipaddress
import random


def create_session_flag(
    server_ip: str,
    server_port: int,
    counter: int,
    device_id: str,
    rng: random.Random | None = None,
) -> str:
    """
    Reimplementation of tdkcloud::P2PManager::CreateSessionFlag().

    Observed behavior from libqv-p2p-v2.so:
    - base = "%8.8x%5.5d%5.5d" % (server_ip_as_u32, server_port, counter)
    - base is right-aligned in a 64-byte string
    - the prefix area is filled with random lowercase letters, except randomly
      chosen unique positions where bytes of device_id[4:] are injected
    """
    if len(device_id) < 4:
        raise ValueError("device_id must be at least 4 characters long")

    rng = rng or random.Random()
    ip_value = int(ipaddress.IPv4Address(server_ip))
    base = f"{ip_value:08x}{server_port:05d}{counter:05d}"
    if len(base) > 64:
        raise ValueError(
            "base session flag seed is unexpectedly longer than 64 bytes"
        )

    prefix_len = 64 - len(base)
    injected = device_id[4:]
    if len(injected) > prefix_len:
        raise ValueError(
            "device_id tail does not fit into session flag prefix"
        )

    chars = ["\x00"] * 64
    chars[prefix_len:] = list(base)
    positions = rng.sample(range(prefix_len), len(injected))
    position_map = dict(zip(positions, injected))

    for index in range(prefix_len):
        chars[index] = position_map.get(
            index, chr(ord("a") + rng.randrange(26))
        )

    return "".join(chars)


def create_request_session_id(
    counter16: int, rng: random.Random | None = None
) -> int:
    """
    Reimplementation of the request-session-id
    composition used by P2PManager::AddPort().

    Native code stores:
    - low  16 bits: incrementing counter
    - high 16 bits: random value
    """
    rng = rng or random.Random()
    return ((rng.randrange(0x10000) & 0xFFFF) << 16) | (counter16 & 0xFFFF)

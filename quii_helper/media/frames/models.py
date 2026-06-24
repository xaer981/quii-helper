from dataclasses import dataclass


@dataclass
class QuiiHeader:
    packet_type: int
    payload_size: int
    raw_size: int
    flag13: int
    flag14: int
    flag15: int
    flag16: int
    flag17: int
    raw: bytes

import queue
from typing import Any

RbUdpPayloadPacket = dict[str, Any]


class RbUdpPayloadQueue:
    """Store decoded RBUDP media payload packets for consumers."""

    def __init__(self) -> None:
        self.data: queue.Queue[RbUdpPayloadPacket] = queue.Queue()

    def queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None:
        self.data.put(
            {
                "payload": payload,
                "source": source,
                "meta": meta,
            }
        )

    def recv_packet(self, timeout: float = 5.0) -> RbUdpPayloadPacket:
        return self.data.get(timeout=timeout)

    def recv_payload(self, timeout: float = 5.0) -> bytes:
        packet = self.recv_packet(timeout=timeout)
        return bytes(packet["payload"])

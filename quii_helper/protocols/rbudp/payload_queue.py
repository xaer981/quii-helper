import queue
from typing import Any


class RbUdpPayloadQueueMixin:
    def _init_payload_queue(self) -> None:
        self._data: "queue.Queue[dict[str, Any]]" = queue.Queue()

    def _queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None:
        self._data.put(
            {
                "payload": payload,
                "source": source,
                "meta": meta,
            }
        )

    def recv_packet(self, timeout: float = 5.0) -> dict[str, Any]:
        return self._data.get(timeout=timeout)

    def recv_payload(self, timeout: float = 5.0) -> bytes:
        packet = self.recv_packet(timeout=timeout)
        return bytes(packet["payload"])

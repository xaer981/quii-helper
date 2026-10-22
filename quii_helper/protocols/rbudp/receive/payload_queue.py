import queue
import threading
import time
from collections import deque
from typing import Any

from quii_helper.support.errors import QuiiConnectionError

RbUdpPayloadPacket = dict[str, Any]
MAX_PENDING_PAYLOAD_PACKETS = 4096
MAX_PENDING_PAYLOAD_BYTES = 32 * 1024 * 1024


class RbUdpPayloadQueue:
    """Bound pending payloads and propagate terminal receiver failures."""

    def __init__(self) -> None:
        self._packets: deque[RbUdpPayloadPacket] = deque()
        self._pending_bytes = 0
        self._condition = threading.Condition()
        self._error: Exception | None = None

    def fail(self, error: Exception) -> None:
        """Abort the stream and wake all readers without returning partial data."""
        with self._condition:
            if self._error is None:
                self._error = error
                self._packets.clear()
                self._pending_bytes = 0
            self._condition.notify_all()

    def raise_if_failed(self) -> None:
        with self._condition:
            if self._error is not None:
                raise QuiiConnectionError(str(self._error)) from self._error

    def queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None:
        with self._condition:
            self.raise_if_failed()
            if (
                len(self._packets) >= MAX_PENDING_PAYLOAD_PACKETS
                or self._pending_bytes + len(payload)
                > MAX_PENDING_PAYLOAD_BYTES
            ):
                self.fail(
                    QuiiConnectionError(
                        "RBUDP pending payload limit exceeded; consumer is too slow"
                    )
                )
                self.raise_if_failed()
            self._packets.append(
                {
                    "payload": payload,
                    "source": source,
                    "meta": meta,
                }
            )
            self._pending_bytes += len(payload)
            self._condition.notify()

    def recv_packet(self, timeout: float = 5.0) -> RbUdpPayloadPacket:
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._packets:
                self.raise_if_failed()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                self._condition.wait(remaining)
            self.raise_if_failed()
            packet = self._packets.popleft()
            self._pending_bytes -= len(packet["payload"])
            return packet

    def get_nowait(self) -> RbUdpPayloadPacket:
        """Consume a queued setup packet using the live sender's queue interface."""
        return self.recv_packet(timeout=0)

    def recv_payload(self, timeout: float = 5.0) -> bytes:
        packet = self.recv_packet(timeout=timeout)
        return bytes(packet["payload"])

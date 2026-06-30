import queue
import time
from typing import Any, Iterator, cast

from quii_helper.models.packets import TunnelPacket


class TunnelPacketStream:
    def __init__(self, tunnel: Any) -> None:
        self.tunnel = tunnel

    def live_packets(
        self,
        *,
        duration: float,
        timeout: float,
        keepalive_credentials: Any | None = None,
    ) -> Iterator[TunnelPacket]:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self._maybe_send_keepalive(keepalive_credentials)
            try:
                yield cast(
                    TunnelPacket,
                    self.tunnel.recv_packet(timeout=min(timeout, 1.0)),
                )
            except queue.Empty:
                continue

    def flush_fragment_partials(
        self, *, drain_seconds: float, timeout: float
    ) -> Iterator[TunnelPacket]:
        self.tunnel.flush_fragment_partials()
        yield from self._drain_until_timeout(
            drain_seconds=drain_seconds, timeout=timeout
        )

    def drain_live(
        self,
        *,
        drain_seconds: float,
        timeout: float,
        keepalive_credentials: Any | None = None,
    ) -> Iterator[TunnelPacket]:
        yield from self._drain_until_timeout(
            drain_seconds=drain_seconds,
            timeout=timeout,
            keepalive_credentials=keepalive_credentials,
            break_on_empty=False,
        )

    def close_and_drain(
        self, *, drain_seconds: float, timeout: float
    ) -> Iterator[TunnelPacket]:
        self.tunnel.close()
        yield from self._drain_until_timeout(
            drain_seconds=drain_seconds, timeout=timeout
        )

    def close(self) -> None:
        self.tunnel.close()

    def _maybe_send_keepalive(self, keepalive_credentials: Any | None) -> None:
        if keepalive_credentials is None:
            return
        keepalive = getattr(self.tunnel, "maybe_send_quii_keepalive", None)
        if keepalive is not None:
            keepalive(keepalive_credentials)

    def _drain_until_timeout(
        self,
        *,
        drain_seconds: float,
        timeout: float,
        keepalive_credentials: Any | None = None,
        break_on_empty: bool = True,
    ) -> Iterator[TunnelPacket]:
        deadline = time.monotonic() + drain_seconds
        while time.monotonic() < deadline:
            self._maybe_send_keepalive(keepalive_credentials)
            try:
                yield cast(
                    TunnelPacket, self.tunnel.recv_packet(timeout=timeout)
                )
            except queue.Empty:
                if break_on_empty:
                    break

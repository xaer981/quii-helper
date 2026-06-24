from collections.abc import Callable

from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)

DebugCallback = Callable[..., None]
PayloadCallback = Callable[..., None]


class RbUdpFragmentPartialEmitter:
    def __init__(
        self, *, debug: DebugCallback, queue_payload: PayloadCallback
    ) -> None:
        self.debug = debug
        self.queue_payload = queue_payload

    def emit_active(
        self, streams: dict[tuple[int, int], RbUdpWrappedFragmentStream]
    ) -> None:
        if not streams:
            return
        for stream in list(streams.values()):
            payload = bytes(stream.payload)
            self.debug(
                "emit_wrapped_fragment_partial",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                start_local_id=stream.start_local_id,
                next_local_id=stream.next_local_id,
                have=len(payload),
                need=stream.inner_total_length,
                missing=stream.missing,
            )
            self.queue_payload(
                payload,
                source="wrapped_fragment_partial",
                word4=stream.word4,
                word8=stream.word8,
                start_local_id=stream.start_local_id,
                next_local_id=stream.next_local_id,
                remote_id=stream.remote_id,
                have=len(payload),
                need=stream.inner_total_length,
                missing=stream.missing,
            )
        streams.clear()

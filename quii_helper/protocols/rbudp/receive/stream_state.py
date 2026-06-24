from collections.abc import Mapping
from dataclasses import dataclass, field

NATIVE_RECEIVE_WINDOW_BYTES = 0x10000


@dataclass
class RbUdpReceiveStreamState:
    word4: int
    word8: int
    next_local_id: int | None = None
    buffer: bytearray = field(default_factory=bytearray)
    cache: dict[int, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class RbUdpReceiveStreamAppendEvent:
    local_id: int
    payload_len: int
    buffered_len: int
    next_local_id: int
    from_cache: bool


def advance_local_id(local_id: int, payload_len: int) -> int:
    return (local_id + payload_len) & 0xFFFFFFFF


def append_receive_stream_payload(
    state: RbUdpReceiveStreamState,
    *,
    local_id: int,
    payload: bytes,
    from_cache: bool = False,
) -> RbUdpReceiveStreamAppendEvent:
    state.buffer.extend(payload)
    state.next_local_id = advance_local_id(local_id, len(payload))
    return RbUdpReceiveStreamAppendEvent(
        local_id=local_id,
        payload_len=len(payload),
        buffered_len=len(state.buffer),
        next_local_id=state.next_local_id,
        from_cache=from_cache,
    )


def drain_receive_stream_cache(
    state: RbUdpReceiveStreamState,
) -> list[RbUdpReceiveStreamAppendEvent]:
    events = []
    while state.next_local_id in state.cache:
        cached_local_id = int(state.next_local_id)
        payload = state.cache.pop(cached_local_id)
        events.append(
            append_receive_stream_payload(
                state,
                local_id=cached_local_id,
                payload=payload,
                from_cache=True,
            )
        )
    return events


def receive_ack_status_word(
    buffered_len: int,
    *,
    receive_window_bytes: int = NATIVE_RECEIVE_WINDOW_BYTES,
) -> int:
    remaining = max(0, receive_window_bytes - buffered_len)
    advertised_window = min(remaining, 0xFFFF)
    return (advertised_window << 16) | 0x0900


def receive_stream_summary(
    stats: Mapping[str, int],
    streams: Mapping[tuple[int, int], RbUdpReceiveStreamState],
) -> dict[str, object]:
    active_streams = [
        {
            "word4": hex(stream.word4),
            "word8": hex(stream.word8),
            "next_local_id": stream.next_local_id,
            "buffered": len(stream.buffer),
            "cached": len(stream.cache),
        }
        for stream in streams.values()
        if stream.buffer or stream.cache
    ]
    return {
        **stats,
        "active": len(active_streams),
        "streams": active_streams,
    }


def has_pending_receive_streams(
    streams: Mapping[tuple[int, int], RbUdpReceiveStreamState],
) -> bool:
    return any(stream.buffer or stream.cache for stream in streams.values())

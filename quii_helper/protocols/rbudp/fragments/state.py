from collections.abc import Mapping

from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)


def initial_fragment_stats() -> dict[str, int]:
    return {
        "started": 0,
        "appended": 0,
        "completed": 0,
        "replayed": 0,
        "replay_acked": 0,
        "restart_acked": 0,
        "gaps": 0,
        "partials": 0,
    }


def is_duplicate_fragment_restart(
    existing: RbUdpWrappedFragmentStream | None,
    *,
    inner_total_length: int,
    incoming_payload_len: int,
) -> bool:
    return bool(
        existing is not None
        and existing.inner_total_length == inner_total_length
        and existing.have >= incoming_payload_len
    )


def classify_fragment_append(*, local_id: int, next_local_id: int) -> str:
    if local_id == next_local_id:
        return "in_order"
    if local_id < next_local_id:
        return "replay"
    return "gap"


def active_fragment_streams_summary(
    streams: Mapping[tuple[int, int], RbUdpWrappedFragmentStream],
) -> list[dict[str, object]]:
    return [
        {
            "word4": hex(stream.word4),
            "word8": hex(stream.word8),
            "start_local_id": stream.start_local_id,
            "next_local_id": stream.next_local_id,
            "have": stream.have,
            "need": stream.inner_total_length,
            "missing": stream.missing,
        }
        for stream in streams.values()
    ]


def wrapped_fragment_summary(
    stats: Mapping[str, int],
    streams: Mapping[tuple[int, int], RbUdpWrappedFragmentStream],
) -> dict[str, object]:
    return {
        **stats,
        "active": len(streams),
        "active_streams": active_fragment_streams_summary(streams),
    }

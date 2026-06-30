PLAY_SYNC_LOG_STAGE_COUNTS = frozenset(
    {18, 35, 37, 41, 48, 49, 53, 60, 61, 67, 68}
)


def normalize_play_sync_iterations(value: int | str | None) -> int:
    return max(0, int(value or 0))


def is_play_sync_exhausted(
    *,
    configured_iterations: int,
    remaining: int,
) -> bool:
    return configured_iterations > 0 and int(remaining) <= 0


def should_log_play_sync_ack(sent_count: int) -> bool:
    return (
        sent_count < 8
        or sent_count in PLAY_SYNC_LOG_STAGE_COUNTS
        or sent_count % 200 == 0
    )


def advance_play_sync_counter(remote_id: int, step: int) -> int:
    return (remote_id + step) & 0xFFFFFFFF


def decrement_play_sync_remaining(remaining: int) -> int:
    if int(remaining) > 0:
        return max(0, int(remaining) - 1)
    return int(remaining)

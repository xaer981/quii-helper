from collections.abc import Mapping


def active_fragmented_media_entry(
    key: tuple[object, ...],
    state: Mapping[str, object],
) -> dict:
    expected_body_len = int(state.get("expected_body_len", 0))
    body = state.get("body", b"")
    have_body_len = len(body) if isinstance(body, bytes) else 0
    return {
        "fragment_key": key,
        "start_msg_index": state.get("start_msg_index"),
        "source": state.get("source"),
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
        "have_body_len": have_body_len,
        "missing_body_len": max(0, expected_body_len - have_body_len),
        "packet_type": hex(int(state.get("packet_type", 0))),
        "frame_tag": hex(int(state.get("frame_tag", 0))),
        "frame_len": state.get("frame_len"),
    }


def active_fragmented_media_summary(
    states: Mapping[tuple[object, ...], Mapping[str, object]],
) -> list[dict] | None:
    active = [
        active_fragmented_media_entry(key, state)
        for key, state in states.items()
    ]
    return active or None


def fragmented_media_summary(
    stats: Mapping[str, int] | None,
    states: Mapping[tuple[object, ...], Mapping[str, object]],
) -> dict[str, object]:
    return {
        **dict(stats or {}),
        "active": active_fragmented_media_summary(states),
    }

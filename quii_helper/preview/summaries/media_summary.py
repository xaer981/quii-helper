from collections.abc import Mapping, Sequence
from typing import Any, cast

from quii_helper.media.frames.parsing import QuiiCFramePack
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264
from quii_helper.models.capture import (
    H264AnalysisSummary,
    MediaCollectionSummary,
)
from quii_helper.preview.summaries.media_summary_state import (
    MEDIA_PACKET_TYPES,
    decoded_media_frames,
    initial_nal_collection_state,
    media_decrypt_stats,
    nal_collection_payload,
    record_frame_nal_summary,
)


def media_message_nal_analysis(
    decoded: Mapping[str, Any],
) -> H264AnalysisSummary:
    frames = decoded_media_frames(decoded)
    frame = frames[0] if frames else None
    if not isinstance(frame, dict):
        return {}
    return _frame_nal_analysis(frame)


def media_collection_summary(
    media_messages: Sequence[Mapping[str, Any]],
) -> MediaCollectionSummary:
    nal_state = initial_nal_collection_state()
    frames, cframe_stats = _stateful_media_frames(media_messages)
    decrypt_stats = media_decrypt_stats(media_messages)

    for frame in frames:
        nal = _frame_nal_analysis(frame)
        record_frame_nal_summary(nal_state, frame, nal)

    return cast(
        MediaCollectionSummary,
        {
            "media_messages": len(media_messages),
            "media_frame_count": len(frames),
            "cframe_pack": cframe_stats,
            **decrypt_stats,
            **nal_collection_payload(nal_state),
        },
    )


def _stateful_media_frames(
    media_messages: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    packer = QuiiCFramePack()
    frames: list[dict[str, Any]] = []
    for decoded in media_messages:
        header = decoded.get("header")
        if header is None or header.packet_type not in MEDIA_PACKET_TYPES:
            continue
        payload = decoded.get("payload", b"")
        if isinstance(payload, bytes):
            frames.extend(packer.feed(payload))
    return frames, dict(packer.stats)


def _frame_nal_analysis(frame: dict[str, Any]) -> H264AnalysisSummary:
    bitstream = frame.get("bitstream", b"")
    nal_offset = int(frame.get("nal_offset", -1))
    if not isinstance(bitstream, bytes) or nal_offset < 0:
        return {}
    return cast(
        H264AnalysisSummary, analyze_annexb_h264(bitstream[nal_offset:])
    )

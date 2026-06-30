from collections.abc import Iterable, Mapping
from typing import Any

from quii_helper.models.capture import (
    H264AnalysisSummary,
    MediaCollectionSummary,
    MediaNalSample,
)

MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}


def media_decrypt_stats(
    media_messages: Iterable[Mapping[str, Any]],
) -> MediaCollectionSummary:
    media_decrypt_packets = 0
    media_decrypt_bytes = 0
    media_decrypt_candidate_packets = 0
    media_decrypt_candidate_bytes = 0

    for decoded in media_messages:
        candidate_len = int(decoded.get("media_decrypt_candidate_len", 0))
        if candidate_len > 0:
            media_decrypt_candidate_packets += 1
            media_decrypt_candidate_bytes += candidate_len
        if decoded.get("media_decrypt_applied"):
            media_decrypt_packets += 1
            media_decrypt_bytes += int(decoded.get("media_decrypt_len", 0))

    return {
        "media_decrypt_candidate_packets": (media_decrypt_candidate_packets),
        "media_decrypt_candidate_bytes": media_decrypt_candidate_bytes,
        "media_decrypt_packets": media_decrypt_packets,
        "media_decrypt_bytes": media_decrypt_bytes,
    }


def frame_nal_sample(
    frame: Mapping[str, Any],
    nal: Mapping[str, Any],
) -> MediaNalSample:
    return {
        "frame_tag": hex(int(frame.get("frame_tag", 0))),
        "frame_len": int(frame.get("frame_len", 0)),
        "cframe_fragments": int(frame.get("cframe_fragments", 0)),
        "nal": {
            "counts": nal.get("counts", {}),
            "has_sps": bool(nal.get("has_sps")),
            "has_pps": bool(nal.get("has_pps")),
            "has_idr": bool(nal.get("has_idr")),
            "nal_units": nal.get("nal_units", [])[:3],
        },
    }


def decoded_media_frames(decoded: Mapping[str, Any]) -> list[dict[str, Any]]:
    frames = decoded.get("media_frames")
    if isinstance(frames, list):
        return [frame for frame in frames if isinstance(frame, dict)]
    frame = decoded.get("media_frame")
    return [frame] if isinstance(frame, dict) else []


def initial_nal_collection_state() -> MediaCollectionSummary:
    return {
        "counts": {},
        "has_sps": False,
        "has_pps": False,
        "has_idr": False,
        "has_vcl": False,
        "keyframes": 0,
        "nal_samples": [],
    }


def record_frame_nal_summary(
    state: MediaCollectionSummary,
    frame: Mapping[str, Any],
    nal: H264AnalysisSummary,
    *,
    sample_limit: int = 6,
) -> None:
    if int(frame.get("frame_tag", -1)) == 0xE1:
        state["keyframes"] += 1

    counts = state["counts"]
    for name, count in dict(nal.get("counts", {})).items():
        counts[name] = counts.get(name, 0) + int(count)

    state["has_sps"] = state["has_sps"] or bool(nal.get("has_sps"))
    state["has_pps"] = state["has_pps"] or bool(nal.get("has_pps"))
    state["has_idr"] = state["has_idr"] or bool(nal.get("has_idr"))
    state["has_vcl"] = state["has_vcl"] or bool(nal.get("has_vcl"))

    nal_samples = state["nal_samples"]
    if nal and len(nal_samples) < sample_limit:
        nal_samples.append(frame_nal_sample(frame, nal))


def nal_collection_payload(
    state: Mapping[str, Any],
) -> MediaCollectionSummary:
    has_sps = bool(state["has_sps"])
    has_pps = bool(state["has_pps"])
    has_vcl = bool(state["has_vcl"])
    return {
        "keyframes": state["keyframes"],
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_idr": bool(state["has_idr"]),
        "has_vcl": has_vcl,
        "counts": state["counts"],
        "nal_samples": state["nal_samples"],
        "decodable_h264_context": bool(has_sps and has_pps and has_vcl),
    }

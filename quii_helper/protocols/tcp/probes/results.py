from typing import Any

from quii_helper.models.capture import MediaArtifactSummary
from quii_helper.protocols.tcp.probes.candidates import (
    QuiiCredentialCandidate,
    QuiiStreamCombo,
)


def sort_compact_summary(compact_summary: list[dict[str, Any]]) -> None:
    compact_summary.sort(
        key=lambda item: (
            0 if item.get("error") else 1,
            item.get("summary", {}).get("max_video_frame_len", 0),
            item.get("summary", {}).get("avg_video_frame_len", 0),
            item.get("summary", {}).get("video_frames", 0),
        ),
        reverse=True,
    )


def tcp_probe_attempt_summary(
    *,
    combo: QuiiStreamCombo,
    credential: QuiiCredentialCandidate,
    result: dict[str, Any],
    extracted: MediaArtifactSummary | None,
) -> dict[str, Any]:
    return {
        "channel": combo.channel,
        "stream": combo.stream,
        "username": credential.username,
        "password_len": len(credential.password),
        "newcn": combo.newcn,
        "credential_label": credential.label,
        "setup_status": result["setup_response"]["status"],
        "setup_crypto_mode": result["setup_response"]["crypto_mode"],
        "dump_file": result["dump_file"],
        "messages": message_summaries(result["messages"]),
        "extracted": extracted,
    }


def tcp_probe_compact_summary(
    *,
    combo: QuiiStreamCombo,
    credential: QuiiCredentialCandidate,
    result: dict[str, Any],
    extracted: MediaArtifactSummary | None,
) -> dict[str, Any]:
    return {
        "channel": combo.channel,
        "stream": combo.stream,
        "newcn": combo.newcn,
        "credential_label": credential.label,
        "setup_status": result["setup_response"]["status"],
        "crypto_mode": result["setup_response"]["crypto_mode"],
        "media_packets": sum(
            1
            for msg in result["messages"]
            if msg.get("header") and msg["header"].packet_type == 0xA0
        ),
        "summary": extracted["summary"] if extracted else {},
        "mp4": extracted["mp4"] if extracted else False,
        "snapshot": extracted["snapshot"] if extracted else False,
        "mp4_path": extracted["mp4_path"] if extracted else "",
        "snapshot_path": extracted["snapshot_path"] if extracted else "",
    }


def tcp_probe_error_summary(
    *,
    combo: QuiiStreamCombo,
    credential: QuiiCredentialCandidate,
    exc: Exception,
    include_username: bool,
) -> dict[str, Any]:
    summary = {
        "channel": combo.channel,
        "stream": combo.stream,
        "credential_label": credential.label,
        "error": str(exc),
    }
    if include_username:
        summary.update(
            {
                "username": credential.username,
                "password_len": len(credential.password),
            }
        )
    return summary


def message_summaries(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for msg in messages:
        if "header" not in msg:
            summaries.append(msg)
            continue
        header = msg["header"]
        payload = msg["payload"]
        summaries.append(
            {
                "type": header.packet_type,
                "payload_size": header.payload_size,
                "raw_size": header.raw_size,
                "status_b": header.raw[11],
                "state_c": header.raw[12],
                "flag13": header.flag13,
                "flag14": header.flag14,
                "flag15": header.flag15,
                "flag16": header.flag16,
                "flag17": header.flag17,
                "payload_preview": payload[:32].hex(),
                "media_len32": int.from_bytes(header.raw[11:15], "little"),
                "start_code_at": payload.find(b"\x00\x00\x01"),
            }
        )
    return summaries

"""Typed payload models for preview packet processing."""

from typing import Any, TypedDict


class PacketMeta(TypedDict, total=False):
    """Metadata attached to a received tunnel packet."""

    src_id: int
    dest_id: int
    local_id: int
    remote_id: int
    from_msg_index: int
    from_chained_msg_index: int
    chained_packet: int
    remainder_len: int
    start_msg_index: int
    end_msg_index: int
    fragments: int
    expected_body_len: int


class TunnelPacket(TypedDict, total=False):
    """Packet yielded by `TunnelPacketStream`."""

    payload: bytes
    source: str
    meta: PacketMeta


class DecodedQuiiMessage(TypedDict, total=False):
    """Decoded QUII blob fields used by the preview pipeline."""

    header: Any
    is_media: bool
    plausible: bool
    offset: int
    read_size: int
    body_available: int
    payload: bytes
    text_preview: str
    frames: list[dict[str, Any]]
    command: int
    packet_type: int
    media_payload_offset: int
    media_encrypted: bool
    media_command_part_len: int
    media_decrypt_candidate_len: int
    media_decrypt_len: int
    media_decrypt_applied: bool
    media_decrypt_selected: bool
    media_raw_score: int
    media_decrypt_score: int


class QuiiPacketSummary(TypedDict, total=False):
    """Structured packet summary emitted for diagnostics."""

    msg_index: int
    message_index: int
    source: str
    blob_len: int
    meta: PacketMeta
    packet_type: str
    payload_size: int
    raw_size: int
    flag15: int
    flag16: int
    flag17: int
    is_media: bool
    media: bool
    plausible: bool
    offset: int
    payload_prefix: str
    text_preview: str
    media_payload_offset: int
    media_encrypted: bool
    media_command_part_len: int
    media_decrypt_candidate_len: int
    media_decrypt_len: int
    media_decrypt_applied: bool
    media_decrypt_selected: bool
    media_raw_score: int
    media_decrypt_score: int
    decode_candidates: list[dict[str, Any]]
    wrapped_tail_analysis: dict[str, Any] | None
    fragment_partial_analysis: dict[str, Any] | None
    fragmented_media: dict[str, Any]
    media_frame_count: int
    frame_tag: str
    frame_len: int
    frame_stamp: int
    width: int
    height: int
    frame_tags: list[str]

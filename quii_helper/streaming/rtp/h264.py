from dataclasses import dataclass

from quii_helper.media.h264.core.annexb import find_start_codes

DEFAULT_H264_PAYLOAD_TYPE = 96
DEFAULT_RTP_CLOCK_RATE = 90_000
DEFAULT_MAX_RTP_PAYLOAD_SIZE = 1200
FU_A_NAL_TYPE = 28


@dataclass(frozen=True)
class RtpPacketizationResult:
    packets: list[bytes]
    next_sequence_number: int


def annexb_nal_units(access_unit: bytes) -> list[bytes]:
    starts = find_start_codes(access_unit)
    if not starts:
        return [access_unit] if access_unit else []

    nal_units = []
    for index, (start, start_code_len) in enumerate(starts):
        payload_start = start + start_code_len
        payload_end = (
            starts[index + 1][0]
            if index + 1 < len(starts)
            else len(access_unit)
        )
        if payload_start < payload_end:
            nal_units.append(access_unit[payload_start:payload_end])
    return nal_units


def build_rtp_header(
    *,
    payload_type: int,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    marker: bool,
) -> bytes:
    return bytes(
        [
            0x80,
            ((0x80 if marker else 0x00) | (payload_type & 0x7F)),
        ]
    ) + (
        (sequence_number & 0xFFFF).to_bytes(2, "big")
        + (timestamp & 0xFFFFFFFF).to_bytes(4, "big")
        + (ssrc & 0xFFFFFFFF).to_bytes(4, "big")
    )


def packetize_h264_access_unit(
    access_unit: bytes,
    *,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    payload_type: int = DEFAULT_H264_PAYLOAD_TYPE,
    max_payload_size: int = DEFAULT_MAX_RTP_PAYLOAD_SIZE,
) -> RtpPacketizationResult:
    nal_units = annexb_nal_units(access_unit)
    packets: list[bytes] = []
    seq = sequence_number
    for nal_index, nal_unit in enumerate(nal_units):
        is_last_nal = nal_index == len(nal_units) - 1
        nal_packets, seq = _packetize_nal_unit(
            nal_unit,
            sequence_number=seq,
            timestamp=timestamp,
            ssrc=ssrc,
            payload_type=payload_type,
            max_payload_size=max_payload_size,
            mark_last_packet=is_last_nal,
        )
        packets.extend(nal_packets)
    return RtpPacketizationResult(
        packets=packets,
        next_sequence_number=seq,
    )


def _packetize_nal_unit(
    nal_unit: bytes,
    *,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    payload_type: int,
    max_payload_size: int,
    mark_last_packet: bool,
) -> tuple[list[bytes], int]:
    if not nal_unit:
        return [], sequence_number

    if len(nal_unit) <= max_payload_size:
        packet = _rtp_packet(
            payload=nal_unit,
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            marker=mark_last_packet,
        )
        return [packet], sequence_number + 1

    return _packetize_fu_a(
        nal_unit,
        sequence_number=sequence_number,
        timestamp=timestamp,
        ssrc=ssrc,
        payload_type=payload_type,
        max_payload_size=max_payload_size,
        mark_last_packet=mark_last_packet,
    )


def _packetize_fu_a(
    nal_unit: bytes,
    *,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    payload_type: int,
    max_payload_size: int,
    mark_last_packet: bool,
) -> tuple[list[bytes], int]:
    if max_payload_size < 3:
        raise ValueError("max_payload_size must leave room for FU-A headers")

    nal_header = nal_unit[0]
    nal_payload = nal_unit[1:]
    fu_indicator = (nal_header & 0xE0) | FU_A_NAL_TYPE
    nal_type = nal_header & 0x1F
    max_fragment_size = max_payload_size - 2
    packets = []
    seq = sequence_number
    offset = 0
    while offset < len(nal_payload):
        fragment = nal_payload[offset : offset + max_fragment_size]
        is_start = offset == 0
        is_end = offset + len(fragment) >= len(nal_payload)
        fu_header = nal_type
        if is_start:
            fu_header |= 0x80
        if is_end:
            fu_header |= 0x40
        packets.append(
            _rtp_packet(
                payload=bytes([fu_indicator, fu_header]) + fragment,
                payload_type=payload_type,
                sequence_number=seq,
                timestamp=timestamp,
                ssrc=ssrc,
                marker=mark_last_packet and is_end,
            )
        )
        seq += 1
        offset += len(fragment)
    return packets, seq


def _rtp_packet(
    *,
    payload: bytes,
    payload_type: int,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    marker: bool,
) -> bytes:
    return (
        build_rtp_header(
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            marker=marker,
        )
        + payload
    )

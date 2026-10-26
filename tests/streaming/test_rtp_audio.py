"""G.711 sample-clock packetization and native packed A/V timestamps."""

import struct
from dataclasses import replace

import pytest

from quii_helper import CameraAudioFrame
from quii_helper.streaming.rtp.clock import RtpMediaClock
from quii_helper.streaming.rtp.g711 import G711Format, packetize_g711

STAMP = (26 << 26) | (10 << 22) | (26 << 17) | (12 << 12)


def audio_frame(codec=4, data=b"x" * 320, milliseconds=0):
    return CameraAudioFrame(data, codec, 8000, 1, STAMP, milliseconds)


@pytest.mark.parametrize(
    "codec,payload,encoding", [(4, 8, "PCMA"), (5, 0, "PCMU")]
)
def test_g711_format(codec, payload, encoding):
    profile = G711Format.from_frame(audio_frame(codec))
    assert profile.payload_type == payload and profile.encoding == encoding


@pytest.mark.parametrize(
    "overrides", [{"codec": 9}, {"sample_rate": 16000}, {"channels": 2}]
)
def test_unknown_or_incompatible_formats_are_not_mislabeled(overrides):
    with pytest.raises(ValueError, match="RTSP audio requires"):
        G711Format.from_frame(replace(audio_frame(), **overrides))


def test_g711_fragments_keep_every_sample_and_wrap_sequence_and_timestamp():
    result = packetize_g711(
        bytes(range(250)) * 10,
        payload_type=8,
        sequence_number=65535,
        timestamp=0xFFFFFF00,
        ssrc=42,
        max_payload_size=1000,
    )
    assert [struct.unpack_from("!H", p, 2)[0] for p in result.packets] == [
        65535,
        0,
        1,
    ]
    assert [struct.unpack_from("!I", p, 4)[0] for p in result.packets] == [
        0xFFFFFF00,
        744,
        1744,
    ]
    assert b"".join(p[12:] for p in result.packets) == bytes(range(250)) * 10
    assert all(p[:2] == b"\x80\x08" for p in result.packets)
    assert result.next_sequence_number & 65535 == 2


@pytest.mark.parametrize("payload,size", [(96, 1200), (8, 0), (8, -1)])
def test_invalid_rtp_parameters_fail(payload, size):
    with pytest.raises(ValueError):
        packetize_g711(
            b"x",
            payload_type=payload,
            max_payload_size=size,
            sequence_number=0,
            timestamp=0,
            ssrc=1,
        )


def test_native_audio_video_clock_ignores_packet_arrival_bursts(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(
        "quii_helper.streaming.rtp.clock.time.monotonic", lambda: now[0]
    )
    clock = RtpMediaClock()
    now[0] = 13.0
    assert clock.timestamp(STAMP, 0, 90000) == 270000
    now[0] = 20.0
    assert clock.timestamp(STAMP, 40, 8000) == 24320
    assert clock.timestamp(STAMP, 50, 90000) == 274500


def test_native_clock_crosses_midnight_without_timezone_conversion(
    monkeypatch,
):
    monkeypatch.setattr(
        "quii_helper.streaming.rtp.clock.time.monotonic", lambda: 0.0
    )
    stamp = (26 << 26) | (10 << 22) | (26 << 17) | (23 << 12) | (59 << 6) | 59
    tomorrow = (26 << 26) | (10 << 22) | (27 << 17)
    clock = RtpMediaClock()
    assert clock.timestamp(stamp, 990, 8000) == 0
    assert clock.timestamp(tomorrow, 10, 8000) == 160


@pytest.mark.parametrize("stamp,ms", [(0, 0), (STAMP, 1000)])
def test_invalid_calendar_is_not_guessed(stamp, ms):
    with pytest.raises(ValueError):
        RtpMediaClock().timestamp(stamp, ms, 8000)

"""Synthetic CPacket fields checked against native getters, not a live device."""

import struct

import pytest

from quii_helper import CameraAudioFrame
from quii_helper.media.cpacket import parse_cpacket_header
from quii_helper.media.cpacket.header import (
    parse_cpacket_header as inspect_cpacket_header,
)
from quii_helper.media.frames.frame_parsing import parse_quii_media_frame_at
from tests.media.frames.test_parsing import _cpacket


def audio_cpacket(
    data=b"encoded-audio", *, codec=4, sample_rate=8000, channels=1, ms=321
):
    packet = bytearray(
        _cpacket(
            data,
            frame_tag=0xE3,
            frame_stamp=0x6AA12345,
            codec=codec,
            fps_raw=channels,
            width=sample_rate,
            height=0,
        )
    )
    struct.pack_into("<H", packet, 12, ms)
    return bytes(packet)


@pytest.mark.parametrize(
    "parser", [parse_cpacket_header, inspect_cpacket_header]
)
def test_both_header_parsers_use_native_audio_offsets_with_prefix(parser):
    # FrameGetCodec / FrameGetChnNum / FrameGetFreq / FrameGetMS in native.
    frame = parser(b"prefix" + audio_cpacket(), 6)
    assert frame["is_audio"]
    assert frame["codec"] == 4
    assert frame["sample_rate"] == 8000
    assert frame["channels"] == 1
    assert frame["frame_ms"] == 321
    assert frame["fps"] == 0
    assert frame["width"] == frame["height"] == 0


@pytest.mark.parametrize(
    "codec,name",
    [(4, "g711_alaw"), (5, "g711_mulaw"), (9, "pcm"), (8, "codec_8")],
)
def test_encoded_payload_and_device_timestamp_are_preserved(codec, name):
    data = b"private-audio-content"
    parsed = parse_quii_media_frame_at(audio_cpacket(data, codec=codec), 0)
    frame = CameraAudioFrame.from_cpacket(parsed)
    assert frame.data == data
    assert frame.codec == codec
    assert frame.codec_name == name
    assert frame.frame_stamp == 0x6AA12345
    assert frame.milliseconds == 321
    assert frame.sample_rate == 8000 and frame.channels == 1
    assert "private-audio-content" not in repr(frame)


@pytest.mark.parametrize(
    "kwargs", [{"sample_rate": 0}, {"channels": 0}, {"ms": 1000}]
)
def test_invalid_audio_metadata_is_rejected(kwargs):
    frame = parse_quii_media_frame_at(audio_cpacket(**kwargs), 0)
    with pytest.raises(ValueError):
        CameraAudioFrame.from_cpacket(frame)


def test_video_frame_cannot_be_mistaken_for_audio():
    frame = parse_quii_media_frame_at(_cpacket(b"video"), 0)
    with pytest.raises(ValueError, match="E3"):
        CameraAudioFrame.from_cpacket(frame)
    assert frame["fps"] == 25
    assert frame["width"] == 960

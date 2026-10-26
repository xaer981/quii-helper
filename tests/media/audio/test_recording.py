"""Host recording policy; no camera/cloud traffic or audio playback."""

from types import SimpleNamespace

import pytest

from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.frames.assembler import (
    assemble_h264_stream_from_messages,
)
from quii_helper.media.frames.frame_parsing import parse_quii_media_frame_at
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket

STAMP = 0x6AA12345


def video(ms=0):
    packet = bytearray(_cpacket(b"video", frame_stamp=STAMP))
    packet[12:14] = ms.to_bytes(2, "little")
    return parse_quii_media_frame_at(bytes(packet), 0)


def audio(ms=0, **kwargs):
    return parse_quii_media_frame_at(audio_cpacket(ms=ms, **kwargs), 0)


def test_recording_ignores_audio_before_video_and_uses_sample_clock():
    recording = AudioRecording()
    recording.feed(audio(data=b"before", ms=0))
    assert not recording.data
    recording.start_video(video(100))
    recording.feed(audio(data=b"a" * 320, ms=140))
    recording.feed(audio(data=b"b" * 320, ms=227))
    assert recording.data == b"a" * 320 + b"b" * 320
    assert recording.offset_seconds == pytest.approx(0.04)
    assert recording.codec == 4
    assert not recording.skipped_reason
    assert "aaaa" not in repr(recording)


def test_audio_leading_video_is_trimmed_across_multiple_packets():
    recording = AudioRecording()
    recording.start_video(video(100))
    recording.feed(audio(data=b"a" * 320, ms=0))
    recording.feed(audio(data=b"b" * 320, ms=40))
    recording.feed(audio(data=b"c" * 320, ms=80))
    assert recording.data == b"c" * 160
    assert recording.offset_seconds == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"codec": 9},
        {"sample_rate": 0},
        {"sample_rate": 16000},
        {"channels": 2},
        {"ms": 1000},
    ],
)
def test_unusable_audio_warns_once_and_falls_back_to_video(kwargs):
    recording = AudioRecording()
    recording.start_video(video())
    with pytest.warns(UserWarning, match="video-only") as warnings:
        recording.feed(audio(**kwargs))
        recording.feed(audio())
    assert len(warnings) == 1
    assert not recording.data
    assert recording.skipped_reason


def test_codec_change_discards_audio_instead_of_mislabeling_it():
    recording = AudioRecording()
    recording.start_video(video())
    recording.feed(audio(data=b"a" * 320))
    with pytest.warns(UserWarning, match="format changed"):
        recording.feed(audio(codec=5))
    assert not recording.data


def test_invalid_device_calendar_keeps_video_usable():
    recording = AudioRecording()
    recording.start_video({"frame_stamp": 0, "frame_ms": 0})
    with pytest.warns(UserWarning, match="video-only"):
        recording.feed(audio())
    assert not recording.data


def test_shared_message_assembler_collects_audio_only_when_requested():
    key = bytearray(
        _cpacket(
            b"\x00\x00\x00\x01\x65idr",
            frame_stamp=STAMP,
        )
    )
    payload = bytes(key) + audio_cpacket(b"g711", ms=40)
    messages = [
        {"header": SimpleNamespace(packet_type=0xA0), "payload": payload}
    ]
    video_only = assemble_h264_stream_from_messages(messages)
    recording = assemble_h264_stream_from_messages(
        messages, collect_audio=True
    )
    assert video_only.audio is None
    assert recording.audio.data == b"g711"
    assert recording.audio.offset_seconds == pytest.approx(0.04)
    assert recording.stream_bytes == video_only.stream_bytes

"""Synthetic vectors for the two inspected CQUIIStreamFile implementations."""

import hashlib
import struct
from dataclasses import replace

import pytest

from quii_helper.device.cgi.models import DeviceRecordFileInfo
from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.protocols.tcp.archive import packets
from quii_helper.support.errors import ConfigurationError

KEY = b"K" * 32
FILENAME = "2_2026-10-29-10-11-12_2026-10-29-10-11-12_7_9_305419896_6_1_32_0"
VIDEO_FILENAME = (
    "2_2026-10-29-10-11-12_2026-10-29-10-12-12_7_9_305419896_6_0_32_0"
)


def record(**kwargs):
    values = dict(
        file_type="picture", file_name=FILENAME, picture_index="00017"
    )
    values.update(kwargs)
    return DeviceRecordFileInfo(**values)


def video_record(**kwargs):
    values = dict(
        file_type="video", file_name=VIDEO_FILENAME, picture_index=""
    )
    values.update(kwargs)
    return record(**values)


def test_video_open_uses_filename_end_time_not_picture_idx():
    descriptor = packets.record_descriptor(video_record())
    assert descriptor.file_info[:11].hex() == "0200cca2ba6a0778563412"
    assert descriptor.file_info[11] == 0
    assert descriptor.file_info[15:] == bytes.fromhex("0ca3ba6a")
    assert (
        packets.record_descriptor(
            video_record(picture_index="999999999999")
        ).file_info
        == descriptor.file_info
    )
    header, _ = plain(packets.open_packet(descriptor, "P" * 64, KEY))
    assert header[0] == 2 and header[24] == 0
    assert header[28:] == bytes.fromhex("0ca3ba6a")


@pytest.mark.parametrize("kind", ["picture", "video"])
@pytest.mark.parametrize("selector", [0, 1, 256, -1])
def test_filename_selector_controls_native_open_tail_not_cgi_media_type(
    kind, selector
):
    name = FILENAME.replace("_6_1_32_0", f"_6_{selector}_32_0")
    descriptor = packets.record_descriptor(
        record(file_type=kind, file_name=name)
    )
    header, _ = plain(packets.open_packet(descriptor, "P" * 64, KEY))
    # ParseURL overwrites the initial type; FillFileInfo branches on the full F18.
    assert header[24] == selector & 255
    tail = (17 if kind == "picture" else 0) if selector else 0x6ABAA2CC
    assert header[28:] == struct.pack("<I", tail)


def test_tantos_video_filename_nonzero_selector_does_not_require_picture_idx():
    entry = video_record(
        file_name="00_2026-10-29-10-11-12_2026-10-29-10-11-42_00_04_0001_00_01_04_4096",
        picture_index="not-a-video-selector",
    )
    descriptor = packets.record_descriptor(entry)
    assert (
        descriptor.file_info.hex() == "0000cca2ba6a00010000000100040000000000"
    )


@pytest.mark.parametrize(
    "name",
    [
        VIDEO_FILENAME.replace(
            "_2026-10-29-10-12-12_", "_2026-10-29-10-10-12_"
        ),
        VIDEO_FILENAME.replace(
            "_2026-10-29-10-12-12_", "_2026-02-30-10-12-12_"
        ),
    ],
)
def test_video_filename_end_time_is_validated(name):
    with pytest.raises(ConfigurationError):
        packets.record_descriptor(video_record(file_name=name))


def plain(wire):
    return (
        aes_cbc_crypt(wire[:32], KEY, crypto_mode=2, decrypt=True),
        aes_cbc_crypt(wire[32:], KEY, crypto_mode=2, decrypt=True),
    )


def test_setup_is_file_not_live_or_talk():
    expected = bytearray(32)
    expected[0], expected[9] = 0xA9, 1
    assert packets.setup_packet() == expected


@pytest.mark.parametrize("index", ["0", "00017", "4294967295"])
def test_file_selectors_match_native_fill_file_info(index):
    picture = packets.record_descriptor(record(picture_index=index))
    # vHome FillFileInfo00519468 / vEye FillFileInfo0052a9e8.
    assert picture.file_info[:15].hex() == "0200cca2ba6a077856341201060901"
    assert picture.file_info[15:] == struct.pack("<I", int(index))
    assert picture.start_stamp == 0x6ABAA2CC


def test_open_has_structured_metadata_not_a_live_url_or_filename(monkeypatch):
    monkeypatch.setattr(packets.time, "time", lambda: 1234567890)
    picture = packets.record_descriptor(record())
    header, extension = plain(packets.open_packet(picture, "P" * 64, KEY))
    body = b"adminapp2&&" + b"P" * 64 + b"\0\0"
    expected = bytearray(32)
    struct.pack_into("<BQHH", expected, 0, 2, 1234567890, 112, len(body))
    expected[13:] = bytes.fromhex("0200cca2ba6a07785634120106090111000000")
    assert header == expected
    assert extension == (
        body + hashlib.sha256(expected + body).digest()
    ).ljust(112, b"\0")
    assert FILENAME.encode() not in extension
    assert b"mode=real" not in extension


def test_seek_mode_and_keepalive_are_header_only_native_commands(monkeypatch):
    monkeypatch.setattr(packets.time, "time", lambda: 1234567890)
    picture = packets.record_descriptor(record())
    for wire, kind in (
        (packets.seek_packet(picture, KEY), 5),
        (packets.playback_mode_packet(KEY), 0x15),
        (packets.keepalive_packet(KEY), 0),
    ):
        header, extension = plain(wire)
        assert header[0] == kind
        assert header[9:11] == b"\x20\0"
        assert extension == hashlib.sha256(header).digest()
        if kind == 5:
            assert header[11:15] == bytes.fromhex("cca2ba6a")
        elif kind == 0x15:
            assert header[29:31] == b"\x01\x01"
        else:
            assert not any(header[11:])


def test_filename_not_cgi_channel_or_url_selects_original_picture():
    original = record()
    changed = replace(
        original,
        channel_id="999",
        end_time="different",
        record_id="not-idx",
        stream="sub",
        frame_rate=1,
        file_size=1,
        url="quii://untrusted.invalid/mode=real",
    )
    assert packets.record_descriptor(changed) == packets.record_descriptor(
        original
    )
    assert packets.record_descriptor(
        record(file_name=FILENAME + ".JPG")
    ) == packets.record_descriptor(original)
    assert packets.record_descriptor(
        record(file_name=FILENAME.replace("_7_", "_\n7_"))
    ) == packets.record_descriptor(original)


@pytest.mark.parametrize(
    "text",
    ["2026-10-29t10:11:13z", "2026-10-29T10:11:13Z", "2026-10-29 10:11:13"],
)
def test_cgi_start_time_selects_seek_but_not_file_identity(text):
    picture = packets.record_descriptor(record(start_time=text))
    original = packets.record_descriptor(record())
    assert picture.file_info == original.file_info
    assert picture.start_stamp == original.start_stamp + 1


def test_signed_filename_flags_keep_native_low_bytes_and_all_32_bits():
    name = FILENAME.replace(
        "_7_9_305419896_6_1_32_0", "_-1_265_-1_262_1_-1_-1"
    )
    info = packets.record_descriptor(record(file_name=name)).file_info
    assert info[6] == 255
    assert info[7:11] == b"\xff" * 4
    assert info[11:15] == bytes([1, 6, 9, 1])


def test_authentication_length_is_validated_before_sending():
    picture = packets.record_descriptor(record())
    with pytest.raises(ConfigurationError, match="authentication body"):
        packets.open_packet(picture, "P" * 65535, KEY)


@pytest.mark.parametrize(
    "overrides",
    [
        {"file_type": ""},
        {"start_time": "not-a-time"},
        {"start_time": 1},
        {"start_time": "2026-10-29T10:11:12+03:00"},
        {"picture_index": ""},
        {"picture_index": "-1"},
        {"picture_index": "4294967296"},
        {"picture_index": "\uff11"},
        {"picture_index": 1},
        {"file_name": "../image.jpg"},
        {"file_name": "20261029.jpg"},
        {"file_name": FILENAME + "&filename=other"},
        {"file_name": FILENAME + "\0"},
        {"file_name": FILENAME.replace("2026-10-29", "2026-02-30")},
        {"file_name": FILENAME.replace("2026-10-29", "2064-10-29")},
        {"file_name": FILENAME.replace("2_2026", "65536_2026")},
    ],
)
def test_invalid_or_unsupported_picture_metadata_fails_closed(overrides):
    with pytest.raises(ConfigurationError):
        packets.record_descriptor(record(**overrides))


def test_wrong_entry_type_has_clear_error():
    with pytest.raises(ConfigurationError, match="CameraDeviceRecordFileInfo"):
        packets.record_descriptor({"filename": FILENAME})

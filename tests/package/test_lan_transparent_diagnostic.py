"""Offline FE observation and opt-in query sequencing; no device requests."""

import importlib
import json
import struct
from unittest.mock import MagicMock, Mock, call

import pytest

from quii_helper import CameraStreamCredentials
from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header

example = importlib.import_module("examples.diagnose_lan_stream")


def reply(command, body):
    raw = bytearray(32)
    raw[0], raw[13] = 0xFE, command
    struct.pack_into("<H", raw, 11, len(body))
    return {
        "header": decode_tcp_header(bytes(raw), crypto_mode=0, key=b"").header,
        "payload": body + b"private-sha-padding",
        "is_media": False,
    }


def media_message(payload, *, kind=0xA0, prefix=0, offset=0):
    raw = bytearray(32)
    raw[0] = kind
    struct.pack_into("<HI", raw, 9, prefix, len(payload) + offset)
    struct.pack_into("<H", raw, 16, offset)
    return {
        "is_media": True,
        "payload": payload,
        "header": decode_tcp_header(bytes(raw), crypto_mode=0, key=b"").header,
    }


def test_chain_waits_for_play_then_advances_once_per_matching_reply():
    session = Mock(play_accepted=False)
    probe = example._ReadonlyDeviceInfoProbe()
    probe.advance(session, 5)
    session.request_device_query.assert_not_called()
    assert probe.summary()["status"] == "waiting_for_play"
    session.play_accepted = True
    probe.advance(session)
    assert probe.summary()["waiting_for"] == 5
    for unrelated in (2, 6, 8, 99, None):
        probe.advance(session, unrelated)
    session.request_device_query.assert_called_once_with(5)
    probe.advance(session, 5)
    assert probe.summary()["waiting_for"] == 6
    probe.advance(session, 5)
    probe.advance(session, 6)
    assert probe.summary()["waiting_for"] == 2
    probe.advance(session, 6)
    probe.advance(session, 2)
    completed = probe.summary()
    for duplicate in (5, 6, 2, 8, None):
        probe.advance(session, duplicate)
    assert session.request_device_query.call_args_list == [
        call(5),
        call(6),
        call(2),
    ]
    assert (
        probe.summary()
        == completed
        == {
            "status": "responses_observed",
            "sent_commands": [5, 6, 2],
            "observed_commands": [5, 6, 2],
            "waiting_for": None,
        }
    )


@pytest.mark.parametrize("commands", [(14,), (5, 6, 2, 14)])
def test_optional_channel_query_is_sent_once_after_play_in_requested_order(
    commands,
):
    session = Mock(play_accepted=False)
    probe = example._ReadonlyDeviceInfoProbe(commands=commands)
    probe.advance(session)
    session.request_device_query.assert_not_called()
    session.play_accepted = True
    probe.advance(session)
    for command in commands:
        probe.advance(session, 8)
        assert probe.summary()["waiting_for"] == command
        probe.advance(session, command)
    for duplicate in commands:
        probe.advance(session, duplicate)
    assert session.request_device_query.call_args_list == [
        call(cmd) for cmd in commands
    ]
    assert probe.summary()["status"] == "responses_observed"


def test_missing_channel_ability_reply_does_not_retry_or_block_media(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(play_accepted=True, stream_switch_pending=False)
    packer = Mock(stats={})
    packer.feed.return_value = []

    def receive(**kwargs):
        clock[0] += 1
        return media_message(b"private-media")

    session.recv_message.side_effect = receive
    probe = example._ReadonlyDeviceInfoProbe(commands=(14,))
    result, _ = example._observe_phase(
        session, packer, name="missing_ability", seconds=3, readonly_info=probe
    )
    session.request_device_query.assert_called_once_with(14)
    assert result["readonly_device_info"]["waiting_for"] == 14
    assert result["readonly_device_info"]["status"] == "waiting_for_reply"
    assert packer.feed.call_count == 3
    assert result["media_packets"]["a0"]["count"] == 3
    assert "private" not in json.dumps(result)


def test_media_packet_statistics_precede_frame_assembly_and_expose_no_body(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(stream_switch_pending=False)
    packer = Mock(stats={})
    packer.feed.return_value = []
    messages = iter(
        [
            media_message(b"private", prefix=16, offset=16),
            media_message(b"xx", prefix=32, offset=32),
            *(
                media_message(b"private", kind=kind)
                for kind in (0xA1, 0xA2, 0xA3)
            ),
        ]
    )

    def receive(**kwargs):
        clock[0] += 1
        return next(messages)

    session.recv_message.side_effect = receive
    result, _ = example._observe_phase(
        session, packer, name="media", seconds=5
    )
    packets = result["media_packets"]
    assert set(packets) == {"a0", "a1", "a2", "a3"}
    assert packets["a0"] == {
        "count": 2,
        "wire_payload_bytes": 57,
        "decoded_payload_bytes": 9,
        "encrypted_prefix_min": 16,
        "encrypted_prefix_max": 32,
        "media_offset_min": 16,
        "media_offset_max": 32,
        "media_encryption_flag": 0,
    }
    assert all(packets[kind]["count"] == 1 for kind in ("a1", "a2", "a3"))
    assert packer.feed.call_count == 5
    assert result["counts"] == {} and result["audio_codec_rate_channels"] == {}
    assert "private" not in json.dumps(result)
    session.request_device_query.assert_not_called()


def test_media_packet_statistics_survive_frame_assembly_failure(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(stream_switch_pending=False)
    packer = Mock(stats={})
    packer.feed.side_effect = ValueError("private-decode-failure")

    def receive(**kwargs):
        clock[0] += 1
        return media_message(b"private")

    session.recv_message.side_effect = receive
    progress = {}
    with pytest.raises(ValueError, match="decode-failure"):
        example._observe_phase(
            session, packer, name="failed", seconds=2, progress=progress
        )
    assert progress["media_packets"]["a0"]["count"] == 1
    assert progress["media_packets"]["a0"]["decoded_payload_bytes"] == 7
    assert "private" not in json.dumps(progress)


@pytest.mark.parametrize("channel", [0, -1, 256, 65535])
def test_channel_ability_cli_rejects_truncation_before_loading_credentials(
    monkeypatch, channel
):
    load = Mock(side_effect=AssertionError("no credential access"))
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    with pytest.raises(SystemExit):
        example.main(
            [
                "--host",
                "127.0.0.1",
                "--channel",
                str(channel),
                "--query-channel-ability",
            ]
        )
    load.assert_not_called()


@pytest.mark.parametrize("enabled", [False, True])
def test_observation_keeps_media_and_safe_fe_metadata_with_or_without_queries(
    monkeypatch, enabled
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(play_accepted=False, stream_switch_pending=False)
    packer = Mock(stats={})
    packer.feed.return_value = [
        {"frame_tag": 0xE3, "codec": 4, "sample_rate": 8000, "channels": 1}
    ]
    messages = iter(
        [
            {"is_media": False, "header": Mock(packet_type=1)},
            reply(8, struct.pack("<I", 1_700_000_000)),
            reply(5, b"\x00\x01"),
            media_message(b"audio"),
            reply(6, b"\x00\x02\x02\x00\x01\xff\xff\x02"),
            reply(2, b"\x00\x00"),
            reply(16, b"private-device-name-auth-key"),
            reply(16, b"private-new-name"),
        ]
    )

    def receive(**kwargs):
        clock[0] += 1
        message = next(messages)
        if message["header"].packet_type == 1:
            session.play_accepted = True
        return message

    session.recv_message.side_effect = receive
    probe = example._ReadonlyDeviceInfoProbe() if enabled else None
    result, _ = example._observe_phase(
        session, packer, name="initial", seconds=8, readonly_info=probe
    )
    assert result["audio_codec_rate_channels"] == {"4/8000/1": 1}
    packer.feed.assert_called_once_with(b"audio")
    metadata = result["transparent_commands"]
    assert set(metadata) == {"02", "05", "06", "08", "10"}
    assert metadata["10"]["count"] == 2
    assert metadata["02"]["last"]["fps_mode_name"] == "high"
    assert metadata["06"]["last"]["camera_count"] == 2
    assert metadata["06"]["last"]["channel_flags"] == [
        {"channel": 1, "enabled": True, "talk_enabled": False},
        {"channel": 2, "enabled": False, "talk_enabled": True},
    ]
    assert "private" not in json.dumps(result)
    if enabled:
        assert session.request_device_query.call_args_list == [
            call(5),
            call(6),
            call(2),
        ]
        assert result["readonly_device_info"]["status"] == "responses_observed"
    else:
        session.request_device_query.assert_not_called()
        assert result["readonly_device_info"] is None


@pytest.mark.parametrize("received", [None, 5, 6, 2])
def test_missing_reply_is_unconfirmed_and_never_stalls_or_retries_media(
    monkeypatch, received
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(play_accepted=True, stream_switch_pending=False)
    probe = example._ReadonlyDeviceInfoProbe()
    packer = Mock(stats={})
    packer.feed.return_value = []

    def receive(**kwargs):
        clock[0] += 1
        if clock[0] == 1 and received is not None:
            return reply(received, b"\x00\x01")
        if clock[0] % 2:
            raise TimeoutError()
        return media_message(b"media")

    session.recv_message.side_effect = receive
    result, _ = example._observe_phase(
        session, packer, name="missing", seconds=6, readonly_info=probe
    )
    summary = result["readonly_device_info"]
    assert summary["status"] == "waiting_for_reply"
    assert summary["waiting_for"] == (6 if received == 5 else 5)
    expected = [call(5), call(6)] if received == 5 else [call(5)]
    assert session.request_device_query.call_args_list == expected
    assert packer.feed.call_count == 3
    assert result["elapsed_seconds"] == 6


def test_malformed_reply_is_reported_without_parsing_trailer_or_blocking_chain(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(play_accepted=True, stream_switch_pending=False)
    probe = example._ReadonlyDeviceInfoProbe()
    messages = iter([reply(5, b""), reply(6, b""), reply(2, b"\xff\x00")])

    def receive(**kwargs):
        clock[0] += 1
        return next(messages)

    session.recv_message.side_effect = receive
    result, _ = example._observe_phase(
        session,
        Mock(stats={}),
        name="malformed",
        seconds=3,
        readonly_info=probe,
    )
    assert (
        result["transparent_commands"]["05"]["last"]["decode_status"]
        == "malformed"
    )
    assert (
        result["transparent_commands"]["06"]["last"]["decode_status"]
        == "malformed"
    )
    assert (
        result["transparent_commands"]["02"]["last"]["decode_status"]
        == "device_error"
    )
    assert result["readonly_device_info"]["status"] == "responses_observed"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "flags,commands",
    [
        (["--query-device-info"], (5, 6, 2)),
        (["--query-channel-ability"], (14,)),
        (["--query-device-info", "--query-channel-ability"], (5, 6, 2, 14)),
    ],
)
def test_main_creates_one_probe_per_connection_and_reuses_it_across_switch(
    monkeypatch, tmp_path, capsys, flags, commands
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        example.CameraStreamCredentials,
        "load",
        Mock(
            return_value=CameraStreamCredentials(
                "test", "K" * 32, "private-auth"
            )
        ),
    )
    factory = MagicMock()
    factory.return_value.__enter__.return_value.play_accepted = True
    monkeypatch.setattr(example, "LanTcpSession", factory)
    monkeypatch.setattr(example, "_keyframe_dimensions", lambda *args: {})
    probes = []

    def observe(*args, readonly_info, name, **kwargs):
        assert isinstance(readonly_info, example._ReadonlyDeviceInfoProbe)
        assert readonly_info.commands == commands
        probes.append(readonly_info)
        return {"phase": name, "cpacket_dimensions": {"352x288": 1}}, b""

    monkeypatch.setattr(example, "_observe_phase", observe)
    example.main(["--host", "127.0.0.1", *flags])
    assert len(probes) == 5
    assert probes[1] is probes[2] and probes[3] is probes[4]
    assert probes[0] is not probes[1] and probes[1] is not probes[3]
    assert "private-auth" not in capsys.readouterr().out

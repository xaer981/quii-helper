"""Receive-only diagnostics using synthetic TCP packets, never a real device."""

import hashlib
import json
import socket
import struct
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.device.security.auth import encode_device_password
from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header
from quii_helper.protocols.tcp.live.session import LanTcpSession
from quii_helper.protocols.tcp.probes import talk as probe
from quii_helper.protocols.tcp.talk.session import LanTalkSession
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import ConfigurationError
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import (
    ScriptedSocket,
    command,
    config,
    encrypt,
    media,
)
from tests.protocols.tcp.test_talk_packets import decrypt
from tests.protocols.tcp.test_talk_session import reply


class IdleSocket(ScriptedSocket):
    """Wait at end of scripted input; EOF/interrupt are explicit test inputs."""

    def __init__(self, responses):
        super().__init__()
        self.chunks.extend(responses)
        self.cancelled = threading.Event()

    def recv(self, size):
        if not self.chunks:
            self.cancelled.wait(min(self.timeout, 0.002))
            if self.closed:
                return b""
            raise socket.timeout()
        return super().recv(size)

    def shutdown(self, how):
        super().shutdown(how)
        self.cancelled.set()


@pytest.fixture
def sockets():
    created = []
    transports = []

    def make(preview=(), talk=None):
        if talk is None:
            talk = [reply(0x0B), reply(0x0C), reply(0x0D)]
        pair = [IdleSocket(preview), IdleSocket(talk)]
        created.extend(pair)
        remaining = iter(pair)

        def factory(host, port):
            assert host == "127.0.0.1" and port == 34567
            sock = next(remaining)
            transport = TcpSocketTransport(host, port)
            transport.connect = lambda **kwargs: setattr(
                transport, "sock", sock
            )
            transport.close = Mock(wraps=transport.close)
            transports.append((transport, sock))
            return transport

        return factory, pair

    yield make
    assert all(transport.close.called for transport, _ in transports)
    assert all(sock.closed for sock in created if sock.sent)
    assert not any(
        t.name == "quii-talk-probe-preview" for t in threading.enumerate()
    )


def audio_wire(data=b"private-audio", **kwargs):
    packet = media(audio_cpacket(data, **kwargs))
    header = bytearray(decrypt(packet[:32]))
    header[0] = 0xA1
    return encrypt(bytes(header)) + packet[32:]


def run(factory, *, oem="synthetic-oem", **kwargs):
    return probe.diagnose_lan_talk(
        config(channel=2, stream=3, connect_timeout=0.1, oem=oem),
        duration_seconds=0.02,
        transport_factory=factory,
        **kwargs,
    )


def test_talk_starts_without_preview_audio_and_never_sends_media(sockets):
    factory, pair = sockets(
        preview=[command(), media(_cpacket(b"video"))],
        talk=[reply(0x0B, mask=3), reply(0x0C), reply(0x0D), audio_wire()],
    )
    report = run(factory)
    assert report["status"] == "completed" and not report["errors"]
    assert report["talk_startup_completed"]
    assert report["codec"] == 4 and report["handshake"]["codec_mask"] == 3
    assert report["handshake"]["c_status"] == 0
    assert report["handshake"]["d_status"] == 0
    assert report["preview"]["audio_frames"] == 0
    assert report["preview"]["video_frames"] == 1
    assert report["talk"]["audio_frames"] == 1
    assert report["talk"]["media_packets"] == {"a1": 1}
    assert not report["wait_for_preview_audio"]
    assert not report["microphone_used"] and not report["audio_transmitted"]
    assert report["preview_channel"] == 2 and report["preview_stream"] == 3
    preview_header = decrypt(pair[0].sent[1][:32])
    assert struct.unpack_from("<H", preview_header, 13)[0] == 2
    assert preview_header[16] == 2
    assert pair[1].sent[0][9] == 2
    headers = [decrypt(wire[:32]) for wire in pair[1].sent[1:]]
    assert [h[0] for h in headers] == [0x0B, 0x0C, 0x0D]
    assert struct.unpack_from("<H", headers[0], 13)[0] == 65535
    assert headers[1][13] == headers[2][13] == 1
    rendered = json.dumps(report)
    for secret in ("private-audio", "synthetic-auth", "K" * 32):
        assert secret not in rendered


@pytest.mark.parametrize(
    "profile,client_id,expected_custom,expected_client",
    [
        ("current", "", None, ""),
        ("vhome", "", "syntheticoem", ""),
        ("veye", "provided-identity", "syntheticoem", "provided-identity"),
        ("veye", "", "syntheticoem", "generated-identity"),
    ],
)
def test_profiles_share_native_identity_fields_without_changing_controls(
    sockets, monkeypatch, profile, client_id, expected_custom, expected_client
):
    generated = Mock(return_value=SimpleNamespace(hex="generated-identity"))
    monkeypatch.setattr(probe, "uuid4", generated)
    factory, pair = sockets(
        preview=[media(audio_cpacket(b"preview-audio"))],
        talk=[reply(0x0B), reply(0x0C), reply(0x0D), audio_wire()],
    )
    report = run(
        factory, oem="synthetic,oem", profile=profile, client_id=client_id
    )
    assert report["status"] == "completed"
    assert report["identity_profile"] == profile
    assert report["identity"] == {
        "custom_id_present": expected_custom is not None,
        "client_id_present": bool(expected_client),
        "shared_between_connections": profile != "current",
    }
    if profile == "veye" and not client_id:
        generated.assert_called_once_with()
    else:
        generated.assert_not_called()
    credentials = (
        b"adminapp2&&" + encode_device_password("synthetic-auth").encode()
    )
    for index, custom in enumerate(
        (
            (
                "/mode=real&idc=2&ids=3&ap=2"
                if expected_custom is None
                else expected_custom
            ),
            expected_custom or "",
        )
    ):
        packet = pair[index].sent[1]
        header, tail = decrypt(packet[:32]), decrypt(packet[32:])
        expected = credentials + b"\0" + custom.encode() + b"\0"
        if expected_client:
            expected += expected_client.encode() + b"\0"
        assert struct.unpack_from("<H", header, 11)[0] == len(expected)
        assert tail[: len(expected)] == expected
        assert (
            tail[len(expected) : len(expected) + 32]
            == hashlib.sha256(header + expected).digest()
        )
        assert not any(tail[len(expected) + 32 :])
        assert header[0] == (1 if index == 0 else 0x0B)
        assert struct.unpack_from("<H", header, 13)[0] == (
            2 if index == 0 else 65535
        )
        assert header[15:18] == (b"\1\2\0" if index == 0 else bytes(3))
    assert [decrypt(w[:32])[0] for w in pair[1].sent[1:]] == [0x0B, 0x0C, 0x0D]
    for source in ("preview", "talk"):
        assert report[source]["audio_frames"] == 1
    rendered = json.dumps(report)
    for private in (
        "syntheticoem",
        "synthetic,oem",
        "provided-identity",
        "generated-identity",
        "synthetic-auth",
        credentials.decode(),
    ):
        assert private not in rendered


@pytest.mark.parametrize(
    "profile,oem,client_id",
    [
        ("unknown", "oem", ""),
        ("current", "oem", "unexpected"),
        ("vhome", "oem", "unexpected"),
        ("vhome", "", ""),
        ("vhome", ",,,", ""),
        ("vhome", None, ""),
        ("vhome", "a\0b", ""),
        ("veye", "x" * 257, "id"),
        ("veye", "oem", "id\0suffix"),
        ("veye", "oem", "\u044f" * 129),
        ("veye", "oem", None),
    ],
)
def test_invalid_profile_metadata_is_rejected_before_transport_creation(
    profile, oem, client_id
):
    factory = Mock()
    with pytest.raises(ConfigurationError):
        run(factory, profile=profile, oem=oem, client_id=client_id)
    factory.assert_not_called()


@pytest.mark.parametrize("session_type", [LanTcpSession, LanTalkSession])
@pytest.mark.parametrize(
    "custom_id,client_id",
    [(None, "client"), ("", ""), ("a\0b", ""), ("oem", "x" * 257)],
)
def test_sessions_validate_identity_before_allocating_transport(
    session_type, custom_id, client_id
):
    factory = Mock()
    with pytest.raises(ConfigurationError):
        session_type(
            config(),
            transport_factory=factory,
            custom_id=custom_id,
            client_id=client_id,
        )
    factory.assert_not_called()


def test_separate_audio_assemblers_and_early_talk_media_count_once(sockets):
    preview_audio = audio_cpacket(b"preview", codec=5)
    talk_audio = audio_cpacket(b"talk")
    factory, _ = sockets(
        preview=[media(preview_audio[:13]), media(preview_audio[13:])],
        talk=[
            reply(0x0B, mask=2),
            media(talk_audio[:10]),
            reply(0x0D),
            media(talk_audio[10:]),
            reply(0x0C),
        ],
    )
    report = run(factory, talk_channel=2)
    assert report["status"] == "completed"
    assert report["codec"] == 5 and report["talk_channel"] == 2
    for source, key, size in (
        ("preview", "5:8000:1", 7),
        ("talk", "4:8000:1", 4),
    ):
        stats = report[source]
        assert stats["audio_frames"] == 1
        assert stats["audio_bytes"] == size
        assert stats["audio_codec_rate_channels"] == {key: 1}
        assert stats["first_audio_seconds"] is not None
    assert report["handshake"]["c_status"] == 0


def test_no_audio_is_not_a_fabricated_handshake_failure(sockets):
    factory, _ = sockets(talk=[reply(0x0B), reply(0x0D)])
    report = run(factory)
    assert report["status"] == "completed"
    assert report["handshake"]["c_status"] is None
    assert report["handshake"]["d_status"] == 0
    assert report["talk"]["audio_frames"] == 0
    assert report["preview"]["first_audio_seconds"] is None


@pytest.mark.parametrize(
    "responses,key,value",
    [
        ([reply(0x0B), audio_wire(), reply(0x0D, status=8)], "d_status", 8),
        ([reply(0x0B, mask=16)], "codec_mask", 16),
        ([reply(0x0B), reply(0x0D, bad_sha=True)], "d_status", None),
        ([reply(0x0B)], "d_status", None),
    ],
)
def test_startup_failure_retains_sanitized_partial_report(
    sockets, responses, key, value
):
    factory, _ = sockets(talk=responses)
    report = run(factory)
    assert report["status"] == "failed"
    assert not report["talk_startup_completed"]
    assert report["errors"][0]["stage"] == "talk_open"
    assert report["handshake"][key] == value
    if value == 8:
        assert report["talk"]["audio_frames"] == 1


def test_preview_error_is_not_empty_audio_and_closes_both_connections(sockets):
    factory, _ = sockets(preview=[OSError("secret error body")])
    report = run(factory)
    assert report["status"] == "failed"
    assert any(e["stage"] == "preview_receive" for e in report["errors"])
    assert "secret error body" not in json.dumps(report)


def test_interrupt_during_talk_handshake_closes_both_connections(sockets):
    factory, _ = sockets(talk=[KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        run(factory)


def test_second_transport_construction_failure_closes_first(monkeypatch):
    transport = Mock()
    factory = Mock(side_effect=[transport, OSError("private factory error")])
    report = run(factory)
    assert report["status"] == "failed"
    assert report["errors"] == [
        {"stage": "talk_create", "type": "OSError", "cause_type": ""}
    ]
    transport.close.assert_called_once()
    transport.connect.assert_not_called()
    assert report["handshake"] == {} and report["codec"] is None


def test_reader_start_failure_closes_both_connections(sockets, monkeypatch):
    factory, pair = sockets()
    monkeypatch.setattr(
        probe.Thread, "start", Mock(side_effect=RuntimeError("start failed"))
    )
    report = run(factory)
    assert report["status"] == "failed"
    assert not pair[1].sent


@pytest.mark.parametrize(
    "duration", [0, -1, 61, True, float("nan"), float("inf")]
)
def test_invalid_duration_before_creating_transports(duration):
    factory = Mock()
    with pytest.raises(ValueError, match="duration_seconds"):
        probe.diagnose_lan_talk(
            config(), duration_seconds=duration, transport_factory=factory
        )
    factory.assert_not_called()


@pytest.mark.parametrize(
    "overrides,selector", [({"connection_mode": "cloud"}, 1), ({}, True)]
)
def test_invalid_connection_inputs_before_creating_transports(
    overrides, selector
):
    factory = Mock()
    with pytest.raises((ConfigurationError, ValueError)):
        probe.diagnose_lan_talk(
            config(**overrides),
            talk_channel=selector,
            transport_factory=factory,
        )
    factory.assert_not_called()


def decoded(payload):
    wire = media(payload)
    header = decode_tcp_header(wire[:32], crypto_mode=2, key=b"K" * 32)
    return {
        "header": header.header,
        "is_media": True,
        "payload": payload,
        "plausible": True,
    }


@pytest.mark.parametrize(
    "limit,value", [("MAX_MESSAGE_BYTES", 3), ("MAX_SOURCE_BYTES", 3)]
)
def test_traffic_has_bounded_media_budget(monkeypatch, limit, value):
    monkeypatch.setattr(probe, limit, value)
    stats = probe._Traffic(0)
    with pytest.raises(ValueError, match="budget"):
        stats.feed(decoded(b"too much"))
    assert stats.summary()["limit_reached"]


def test_partial_frame_cannot_accumulate_beyond_diagnostic_budget(monkeypatch):
    monkeypatch.setattr(probe, "MAX_MESSAGE_BYTES", 32)
    packet = audio_cpacket(b"x" * 100)
    stats = probe._Traffic(0)
    stats.feed(decoded(packet[:20]))
    with pytest.raises(ValueError, match="partial-frame budget"):
        stats.feed(decoded(packet[20:40]))
    assert stats.summary()["limit_reached"]
    assert stats.summary()["audio_frames"] == 0


def test_audio_metadata_validation_and_buckets_are_bounded(monkeypatch):
    monkeypatch.setattr(probe, "MAX_FORMATS", 1)
    stats = probe._Traffic(0)
    for packet in (
        audio_cpacket(codec=4),
        audio_cpacket(codec=5),
        audio_cpacket(channels=0),
    ):
        stats.feed(decoded(packet))
    report = stats.summary()
    assert report["audio_frames"] == 3
    assert report["invalid_audio_frames"] == 1
    assert report["audio_codec_rate_channels"] == {"4:8000:1": 1}
    assert report["other_formats"] == 1


@pytest.mark.parametrize("profile", ["current", "vhome", "veye"])
def test_example_uses_saved_key_for_lan_only_without_microphone(
    monkeypatch, capsys, profile
):
    from examples import diagnose_lan_talk as example

    saved = Mock(stream_key="saved-key", auth_code="saved-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", Mock(return_value=saved)
    )
    monkeypatch.setattr(
        example, "load_config", lambda: config(connection_mode="cloud")
    )
    diagnostic = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(example, "diagnose_lan_talk", diagnostic)
    example.main([] if profile == "current" else ["--profile", profile])
    used_config = diagnostic.call_args.args[0]
    assert used_config.connection_mode == "lan"
    assert (
        used_config.stream_key == "saved-key"
        and used_config.auth_code == "saved-auth"
    )
    assert diagnostic.call_args.kwargs == {
        "duration_seconds": 10,
        "talk_channel": 65535,
        "profile": profile,
    }
    assert json.loads(capsys.readouterr().out) == {"status": "completed"}


def test_example_rejects_unknown_profile_before_loading_credentials(
    monkeypatch,
):
    from examples import diagnose_lan_talk as example

    saved = Mock()
    monkeypatch.setattr(example.CameraStreamCredentials, "load", saved)
    with pytest.raises(SystemExit) as exc:
        example.main(["--profile", "unknown"])
    assert exc.value.code == 2
    saved.assert_not_called()

"""Offline tests for the ``pipelined`` archive protocol variant.

Firmware such as the Intelbras Allo wT7 is silent to a bare Open and
authenticates the file channel with the cloud ``dynamic-password`` instead of
``auth_code``. These tests exercise that variant against the same scripted TCP
peer as the default path; no device, cloud, or real credentials are involved.
"""

import pytest

from quii_helper.protocols.tcp.archive import download
from quii_helper.support.errors import ConfigurationError
from tests.protocols.tcp.test_archive_download import JPEG, cpacket, peer
from tests.protocols.tcp.test_archive_packets import plain, record
from tests.protocols.tcp.test_lan_session import command, config, media


def test_pipelined_uses_dynamic_password_auth_and_pipelines_sequence():
    # The device replies to Open and then streams the JPEG; the variant stops
    # on the EOI without needing a trailing command frame.
    sock, _, factory = peer([command(2), media(cpacket())])
    out = download.download_record_bytes(
        config(dynamic_password="dynpass-123", oem="A0077,G0077"),
        record(),
        transport_factory=factory,
        protocol="pipelined",
    )
    assert out == JPEG
    assert sock.closed
    # Open/Seek/Playback/0x07 are sent up front (default path sends [2, 5, 0x15]).
    assert [plain(packet)[0][0] for packet in sock.sent[1:]] == [2, 5, 0x15, 7]
    # The Open body is the dynamic-password form, not adminapp2&& + auth_code.
    _, extension = plain(sock.sent[1])
    assert extension.startswith(b"adminapp&&dynpass-123.A0077G0077.")


def test_pipelined_requires_dynamic_password():
    _, _, factory = peer([command(2), media(cpacket())])
    with pytest.raises(ConfigurationError, match="dynamic_password"):
        download.download_record_bytes(
            config(), record(), transport_factory=factory, protocol="pipelined"
        )


def test_unknown_archive_protocol_is_rejected():
    _, _, factory = peer([command(2), media(cpacket())])
    with pytest.raises(ConfigurationError, match="protocol"):
        download.download_record_bytes(
            config(), record(), transport_factory=factory, protocol="bogus"
        )


def test_default_protocol_keeps_auth_code_open_and_waits_for_reply():
    # Regression guard: the default path is unchanged — adminapp2&& auth and no
    # 0x07, and it still needs the Open reply before Seek/Playback.
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    assert (
        download.download_record_bytes(
            config(), record(), transport_factory=factory
        )
        == JPEG
    )
    assert [plain(packet)[0][0] for packet in sock.sent[1:]] == [2, 5, 0x15]
    _, extension = plain(sock.sent[1])
    assert extension.startswith(b"adminapp2&&")

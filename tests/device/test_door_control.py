import base64
import hashlib
import http.client
import io
import ssl
import urllib.error
import urllib.request
import urllib.response
import xml.etree.ElementTree as ET
from email.message import Message
from typing import Any
from unittest.mock import MagicMock

import pytest

from quii_helper.device.control import CameraDoorOpenResult, request_open_door
from quii_helper.device.http.xml import build_request_xml
from quii_helper.device.security.auth import device_supports_sha256_password
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError
from quii_helper.support.log import logger

SUCCESS_XML = b"<envelope><body><error>0</error></body></envelope>"


@pytest.fixture
def opener(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.open.return_value.__enter__.return_value.read.return_value = (
        SUCCESS_XML
    )
    monkeypatch.setattr(
        urllib.request, "build_opener", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        MagicMock(side_effect=AssertionError("unexpected network request")),
    )
    return client


def _request(**overrides: Any) -> CameraDoorOpenResult:
    options: dict[str, Any] = {
        "host": "192.0.2.10",
        "auth_code": "test-cgi-auth",
        "unlock_password": "test-door-password",
        "channel": 2,
        "lock_number": 1,
        "password_mode": "sha256",
    }
    options.update(overrides)
    return request_open_door(**options)


def test_request_matches_native_device_unlock_xml(opener: MagicMock) -> None:
    result = _request(port=8080)

    opener.open.assert_called_once()
    request = opener.open.call_args.args[0]
    assert request.full_url == "http://192.0.2.10:8080/tdkcgi"
    assert request.method == "POST"
    root = ET.fromstring(request.data)
    assert ["body", "header"] == [item.tag for item in root]
    assert root.findtext("./body/command") == "set.device.opendoor"
    content = root.find("./body/content")
    assert content is not None
    assert content.attrib == {
        "class": "com.quvii.qvweb.device.bean.requset.DeviceUnlockContent"
    }
    assert ["door", "locknumber", "password"] == [item.tag for item in content]
    assert content.findtext("door") == "2"
    assert content.findtext("locknumber") == "1"
    assert (
        content.findtext("password")
        == hashlib.sha256(b"test-door-password").hexdigest()
    )
    assert (
        root.findtext("./header/password")
        == hashlib.sha256(b"test-cgi-auth").hexdigest()
    )
    assert root.findtext("./header/passwordencode") == "1"
    assert root.findtext("./header/username") == "adminapp2"
    assert root.findtext("./header/security") == "username"
    assert result == CameraDoorOpenResult(error=0, channel=2, lock_number=1)
    assert result.accepted
    assert "accepted" in result.message


def test_preencoded_password_is_not_hashed_again(opener: MagicMock) -> None:
    encoded = hashlib.sha256(b"test-door-password").hexdigest()

    _request(unlock_password=encoded)

    root = ET.fromstring(opener.open.call_args.args[0].data)
    assert root.findtext("./body/content/password") == encoded


@pytest.mark.parametrize(
    ("mode", "capability", "encoded"),
    [
        ("auto", True, True),
        ("auto", False, False),
        ("plain", None, False),
        ("sha256", None, True),
        ("plain", True, False),
        ("sha256", False, True),
    ],
)
def test_body_password_format_follows_capability_or_explicit_mode(
    opener: MagicMock, mode: str, capability: bool | None, encoded: bool
) -> None:
    password = 'test-password<&"'
    _request(
        unlock_password=password,
        password_mode=mode,
        supports_sha256_password=capability,
    )

    root = ET.fromstring(opener.open.call_args.args[0].data)
    assert root.findtext("./body/content/password") == (
        hashlib.sha256(password.encode()).hexdigest() if encoded else password
    )
    assert (
        root.findtext("./header/password")
        == hashlib.sha256(b"test-cgi-auth").hexdigest()
    )
    opener.open.assert_called_once()


def test_auto_unknown_capability_never_sends(opener: MagicMock) -> None:
    with pytest.raises(ConfigurationError, match="capability.*unknown"):
        _request(password_mode="auto")

    opener.open.assert_not_called()


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\x01\x0e" + bytes(14), False),
        (b"\x01\x0e\x00\x00\x00\x01" + bytes(10), True),
        (b"\x01\x0e\x00\x00\x01\x00" + bytes(10), False),
        (b"\x01\x0e\x00\x00\x00\x02" + bytes(10), False),
        (b"", None),
        (b"\x01\x0e\x00\x00\x00", None),
    ],
)
def test_capability_24_matches_native_header_offset_and_bit_order(
    data: bytes, expected: bool | None
) -> None:
    basedata = base64.b64encode(data).decode()

    assert device_supports_sha256_password(basedata) is expected
    assert device_supports_sha256_password(f" \n{basedata}\r\n") is expected


@pytest.mark.parametrize("basedata", ["not-base64!", "AQ4AA", "\u044f"])
def test_malformed_capability_remains_unknown(basedata: str) -> None:
    assert device_supports_sha256_password(basedata) is None


@pytest.mark.parametrize("verify_tls", [True, False])
def test_https_keeps_certificate_verification_setting(
    opener: MagicMock, verify_tls: bool
) -> None:
    _request(scheme="https", verify_tls=verify_tls)

    handler = urllib.request.build_opener.call_args.args[1]
    assert isinstance(handler, urllib.request.HTTPSHandler)
    assert handler._context.check_hostname is verify_tls
    assert handler._context.verify_mode == (
        ssl.CERT_REQUIRED if verify_tls else ssl.CERT_NONE
    )
    assert opener.open.call_args.args[0].full_url.startswith("https://")


def test_existing_xml_content_child_shape_is_preserved() -> None:
    root = ET.fromstring(
        build_request_xml(
            "get.example",
            "username",
            "user",
            "test-password",
            content=ET.Element("alarm"),
        )
    )
    assert root.find("./body/content/alarm") is not None


@pytest.mark.parametrize(
    "raw",
    [
        b"not XML",
        b"<envelope />",
        b"<envelope><body /></envelope>",
        b"<envelope><body><error /></body></envelope>",
        b"<envelope><body><error> </error></body></envelope>",
        b"<envelope><body><error>false</error></body></envelope>",
        b"<envelope><body><error>0.0</error></body></envelope>",
        b"<envelope><body><error>0_0</error></body></envelope>",
        b"<envelope><body><error>0<error>-3</error></error></body></envelope>",
        b"<envelope><body><error>0</error><error>-3</error></body></envelope>",
        b"<envelope><body><error>0</error></body><body /></envelope>",
        b"<other><body><error>0</error></body></other>",
    ],
)
def test_malformed_response_is_unknown_and_never_retried(
    opener: MagicMock, raw: bytes
) -> None:
    opener.open.return_value.__enter__.return_value.read.return_value = raw

    with pytest.raises(QuiiConnectionError, match="device may have acted"):
        _request()

    opener.open.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        urllib.error.URLError("test"),
        http.client.IncompleteRead(b"<envelope>"),
    ],
)
def test_transport_failure_is_unknown_and_never_retried(
    opener: MagicMock, error: Exception
) -> None:
    opener.open.side_effect = error

    with pytest.raises(QuiiConnectionError, match="not retried"):
        _request()

    opener.open.assert_called_once()


def test_redirect_is_rejected_without_a_second_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    headers["Location"] = "http://192.0.2.20/tdkcgi"
    response = urllib.response.addinfourl(
        io.BytesIO(b""), headers, "http://192.0.2.10/tdkcgi", 302
    )
    response.msg = "Found"
    http_open = MagicMock(return_value=response)
    monkeypatch.setattr(urllib.request.HTTPHandler, "http_open", http_open)

    with pytest.raises(QuiiConnectionError, match="not confirmed"):
        _request()

    http_open.assert_called_once()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("channel", 0),
        ("channel", True),
        ("channel", 1.5),
        ("lock_number", -1),
        ("lock_number", False),
        ("port", 0),
        ("port", 65536),
        ("scheme", "ftp"),
        ("host", ""),
        ("auth_code", ""),
        ("unlock_password", " "),
        ("password_mode", "invalid"),
    ],
)
def test_invalid_configuration_never_sends(
    opener: MagicMock, field: str, value: object
) -> None:
    with pytest.raises(ConfigurationError):
        _request(**{field: value})

    opener.open.assert_not_called()


@pytest.mark.parametrize(
    ("code", "description"),
    [
        (-7, "lock is disabled"),
        (-6, "channel is disabled"),
        (-5, "device was locked"),
        (-4, "device is busy"),
        (-3, "door-opening password is incorrect"),
        (999999, "unknown vendor error code"),
    ],
)
def test_device_rejection_uses_unlock_error_meanings(
    opener: MagicMock, code: int, description: str
) -> None:
    opener.open.return_value.__enter__.return_value.read.return_value = (
        f"<envelope><body><error>{code}</error></body></envelope>".encode()
    )

    result = _request()

    assert result.error == code
    assert not result.accepted
    assert description in result.message
    opener.open.assert_called_once()


@pytest.mark.parametrize("mode", ["plain", "sha256"])
def test_debug_logs_redact_both_passwords(
    opener: MagicMock, mode: str
) -> None:
    messages: list[str] = []
    sink = logger.add(
        lambda message: messages.append(str(message)), level="DEBUG"
    )
    try:
        _request(debug=True, password_mode=mode)
    finally:
        logger.remove(sink)

    output = "".join(messages)
    assert "set.device.opendoor" in output
    assert output.count("[REDACTED]") >= 2
    for password in (b"test-cgi-auth", b"test-door-password"):
        assert password.decode() not in output
        assert hashlib.sha256(password).hexdigest() not in output

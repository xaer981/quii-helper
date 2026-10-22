import gzip
import io
import urllib.error
import urllib.request
from email.message import Message
from http.cookiejar import CookieJar
from unittest.mock import Mock

import pytest

from quii_helper.cloud.http import transport
from quii_helper.support.errors import QuiiConnectionError

XML = (
    b"<envelope><header><result>0</result>"
    b"<session>private-session</session></header><content>"
    b"<recordresurl>https://media.example/private-video</recordresurl>"
    b"<recordsubresurl>https://media.example/private-image</recordsubresurl>"
    b"<text>hello</text></content></envelope>"
)


class _Response:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self.body = body
        self.headers = Message()
        for name, value in headers.items():
            self.headers[name] = value
        self.status = 200

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def read(self) -> bytes:
        return self.body

    def info(self) -> Message:
        return self.headers


@pytest.fixture
def opener(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mocked = Mock()
    mocked.open.return_value = _Response(
        XML, {"Content-Type": "application/xml"}
    )
    monkeypatch.setattr(
        transport, "build_cloud_opener", Mock(return_value=mocked)
    )
    return mocked


@pytest.mark.parametrize("encoding", [None, "identity", "gzip", "GZip"])
def test_http_xml_negotiates_and_decodes_only_supported_compression(
    opener: Mock, encoding: str | None
) -> None:
    headers = {"Content-Type": "application/xml; charset=utf-8"}
    if encoding is not None:
        headers["cOnTeNt-EnCoDiNg"] = encoding
    body = (
        gzip.compress(XML) if encoding and encoding.lower() == "gzip" else XML
    )
    opener.open.return_value = _Response(body, headers)

    root, raw = transport.request_userauth(
        b"<request/>",
        auth_url="https://alarm.example/UserAlarm",
        verify_tls=False,
    )

    assert root.findtext("content/text") == "hello"
    assert raw == XML.decode("utf-8")
    assert opener.open.call_count == 1
    request = opener.open.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.data == b"<request/>"
    assert (
        dict((key.lower(), value) for key, value in request.header_items())[
            "accept-encoding"
        ]
        == "gzip"
    )


@pytest.mark.parametrize("isolated", [False, True])
def test_request_uses_an_explicit_or_fresh_cookie_jar(
    opener: Mock,
    monkeypatch: pytest.MonkeyPatch,
    isolated: bool,
) -> None:
    factory = transport.build_cloud_opener
    jar = CookieJar() if isolated else None
    transport.request_userauth(
        b"<request/>",
        auth_url="https://alarm.example",
        cookie_jar=jar,
    )
    used_jar = factory.call_args.kwargs["cookie_jar"]
    assert isinstance(used_jar, CookieJar)
    assert jar is None or used_jar is jar
    factory.assert_called_once_with(verify_tls=True, cookie_jar=used_jar)
    request = opener.open.call_args.args[0]
    assert request.get_header("Cookie") is None


def test_cookie_round_trip_uses_isolated_jar_across_opener_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jar = CookieJar()
    first = transport.build_cloud_opener(verify_tls=False, cookie_jar=jar)
    processor = next(
        handler
        for handler in first.handlers
        if isinstance(handler, urllib.request.HTTPCookieProcessor)
    )
    assert processor.cookiejar is jar
    processor.http_response(
        urllib.request.Request("https://alarm.example/UserAlarm"),
        _Response(b"", {"Set-Cookie": "alarm_session=private-alarm; Path=/"}),
    )
    second = transport.build_cloud_opener(verify_tls=False, cookie_jar=jar)
    processor = next(
        handler
        for handler in second.handlers
        if isinstance(handler, urllib.request.HTTPCookieProcessor)
    )
    request = urllib.request.Request("https://alarm.example/UserAlarm")
    processor.http_request(request)
    assert request.get_header("Cookie") == "alarm_session=private-alarm"
    assert transport.dump_cookie_jar() == []
    assert transport.dump_cookie_jar(cookie_jar=jar) == [
        "alarm_session=[REDACTED]"
    ]


def test_default_openers_never_share_previous_account_cookies():
    first = transport.build_cloud_opener()
    second = transport.build_cloud_opener()
    processors = [
        next(
            handler
            for handler in opener.handlers
            if isinstance(handler, urllib.request.HTTPCookieProcessor)
        )
        for opener in (first, second)
    ]
    processors[0].http_response(
        urllib.request.Request("https://auth.example/login"),
        _Response(b"", {"Set-Cookie": "session=synthetic-account-a; Path=/"}),
    )
    assert processors[0].cookiejar is not processors[1].cookiejar
    request = urllib.request.Request("https://auth.example/login")
    processors[1].http_request(request)
    assert request.get_header("Cookie") is None


def test_default_requests_allocate_independent_cookie_jars(opener):
    factory = transport.build_cloud_opener
    for _ in range(2):
        transport.request_userauth(
            b"<request/>", auth_url="https://auth.example"
        )
    first, second = [
        call.kwargs["cookie_jar"] for call in factory.call_args_list
    ]
    assert isinstance(first, CookieJar) and isinstance(second, CookieJar)
    assert first is not second


@pytest.mark.parametrize("encoding", ["br", "deflate", "gzip, br"])
def test_unadvertised_compression_is_rejected_explicitly(
    opener: Mock, encoding: str
) -> None:
    opener.open.return_value = _Response(
        b"private-body", {"Content-Encoding": encoding}
    )
    with pytest.raises(
        QuiiConnectionError, match="Content-Encoding"
    ) as exc_info:
        transport.request_userauth(
            b"<request/>", auth_url="https://alarm.example"
        )
    assert "private-body" not in str(exc_info.value)
    assert opener.open.call_count == 1


@pytest.mark.parametrize("body", [b"private-body", gzip.compress(XML)[:12]])
def test_broken_gzip_is_not_parsed_or_exposed(
    opener: Mock, body: bytes
) -> None:
    opener.open.return_value = _Response(body, {"Content-Encoding": "gzip"})
    with pytest.raises(QuiiConnectionError, match="invalid gzip") as exc_info:
        transport.request_userauth(
            b"<request/>", auth_url="https://alarm.example"
        )
    assert "private-body" not in str(exc_info.value)


def test_non_xml_error_reports_http_metadata_without_body(
    opener: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = Mock()
    monkeypatch.setattr(transport, "logger", logger)
    opener.open.return_value = _Response(
        b"HTTP/1.1 private-response", {"Content-Type": "text/plain"}
    )
    with pytest.raises(QuiiConnectionError, match="not valid XML") as exc_info:
        transport.request_userauth(
            b"<request/>", auth_url="https://alarm.example", debug=True
        )
    message = str(exc_info.value)
    assert "status=200" in message
    assert "content_type='text/plain'" in message
    assert "content_encoding='identity'" in message
    assert "private-response" not in message
    logger.debug.assert_not_called()


def test_gzip_debug_output_redacts_decoded_session_and_resource_urls(
    opener: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = Mock()
    monkeypatch.setattr(transport, "logger", logger)
    opener.open.return_value = _Response(
        gzip.compress(XML), {"Content-Encoding": "gzip"}
    )
    transport.request_userauth(
        XML, auth_url="https://alarm.example", debug=True
    )
    output = str(logger.debug.call_args_list)
    assert "private-session" not in output
    assert "private-video" not in output
    assert "private-image" not in output
    assert "hello" in output


@pytest.mark.parametrize("body", [gzip.compress(XML), b"private-body"])
def test_compressed_http_error_preserves_status_and_redacts_debug_body(
    opener: Mock, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    logger = Mock()
    monkeypatch.setattr(transport, "logger", logger)
    headers = Message()
    headers["Content-Encoding"] = "gzip"
    error = urllib.error.HTTPError(
        "https://alarm.example", 403, "Forbidden", headers, io.BytesIO(body)
    )
    opener.open.side_effect = error
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        transport.request_userauth(
            XML, auth_url="https://alarm.example", debug=True
        )
    assert exc_info.value is error
    assert opener.open.call_count == 1
    output = str(logger.debug.call_args_list)
    for private in ("private-session", "private-video", "private-body"):
        assert private not in output

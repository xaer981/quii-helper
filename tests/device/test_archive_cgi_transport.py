"""Verify the direct archive CGI policy without connecting any sockets."""

import http.client
from email.message import Message
from functools import partial
from io import BytesIO
from urllib import request
from urllib.error import HTTPError
from urllib.response import addinfourl

import pytest

from quii_helper.device.cgi.client import (
    request_product_info,
    request_record_message_info,
    request_record_session_info,
)

HOST = "192.0.2.10"
ARCHIVE_REQUESTS = [
    partial(
        request_record_session_info,
        start_time="2026-11-27t00:00:00z",
        end_time="2026-11-27t23:59:59z",
    ),
    partial(request_record_message_info, session_id="synthetic-session"),
]


@pytest.mark.parametrize(
    "read, expected_host",
    [
        (ARCHIVE_REQUESTS[0], HOST),
        (ARCHIVE_REQUESTS[1], HOST),
        (request_product_info, "proxy.invalid"),
    ],
    ids=["session", "message", "non-archive"],
)
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_only_archive_cgi_bypasses_the_configured_proxy(
    monkeypatch, read, expected_host, scheme
):
    monkeypatch.setattr(
        request, "getproxies", lambda: {scheme: "http://proxy.invalid:8888"}
    )
    monkeypatch.setattr(request, "proxy_bypass", lambda host: False)
    monkeypatch.setattr(request, "_opener", None)
    attempts = []

    def stop_before_connect(connection):
        attempts.append(connection.host)
        raise OSError("synthetic stop before connect")

    monkeypatch.setattr(
        http.client.HTTPConnection, "connect", stop_before_connect
    )
    monkeypatch.setattr(
        http.client.HTTPSConnection, "connect", stop_before_connect
    )
    with pytest.raises(OSError, match="synthetic stop before connect"):
        read(host=HOST, auth_code="synthetic-auth", scheme=scheme)
    assert attempts == [expected_host]


@pytest.mark.parametrize("read", ARCHIVE_REQUESTS, ids=["session", "message"])
def test_archive_cgi_does_not_follow_redirects(monkeypatch, read):
    attempts = []

    def fake_opener(handler, req):
        attempts.append(req.full_url)
        headers = Message()
        headers["Location"] = "http://redirect.invalid/"
        response = addinfourl(BytesIO(), headers, req.full_url, 302)
        response.msg = "Found"
        return response

    monkeypatch.setattr(request.HTTPHandler, "http_open", fake_opener)
    with pytest.raises(HTTPError) as error:
        read(host=HOST, auth_code="synthetic-auth")
    assert error.value.code == 302
    assert attempts == [f"http://{HOST}:80/tdkcgi"]

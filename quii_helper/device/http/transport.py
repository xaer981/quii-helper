import json
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, cast

from quii_helper.device.http.json import build_common_json_request
from quii_helper.device.http.xml import build_request_xml
from quii_helper.device.security.auth import get_encrypt_password
from quii_helper.support import redaction
from quii_helper.support.log import logger


def request_cgi(
    command: str,
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    encrypted: bool,
    nc: str | None = None,
    scheme: str = "http",
    passwordencode: str | None = None,
    content: ET.Element | None = None,
    debug: bool = False,
    verify_tls: bool = True,
) -> dict[str, str]:
    if encrypted:
        security = "usernametoken"
        request_password = get_encrypt_password(username, password, str(nc))
    else:
        security = "username"
        request_password = password

    xml_body = build_request_xml(
        command,
        security,
        username,
        request_password,
        nc=nc,
        passwordencode=passwordencode,
        content=content,
    )
    data = _post_cgi_xml(
        xml_body,
        host=host,
        port=port,
        scheme=scheme,
        debug=debug,
        verify_tls=verify_tls,
    )
    if debug:
        _debug_exchange(xml_body, data)

    root = ET.fromstring(data)
    body = root.find("./body")
    if body is None:
        raise RuntimeError("response body not found")

    error = (body.findtext("error") or "0").strip()
    return {
        "error": error,
        "raw": data.decode("utf-8", errors="replace"),
    }


def request_json_cgi(
    command: str,
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    encrypted: bool,
    nc: str | None = None,
    scheme: str = "http",
    passwordencode: int = 1,
    content: dict[str, Any] | None = None,
    debug: bool = False,
    verify_tls: bool = True,
) -> dict[str, Any]:
    if encrypted:
        security = "usernametoken"
        request_password = get_encrypt_password(username, password, str(nc))
    else:
        security = "username"
        request_password = password

    json_body = build_common_json_request(
        command,
        security=security,
        username=username,
        password=request_password,
        passwordencode=passwordencode,
        content=content,
    )
    data = _post_cgi_json(
        json_body,
        host=host,
        port=port,
        scheme=scheme,
        debug=debug,
        verify_tls=verify_tls,
    )
    if debug:
        _debug_json_exchange(json_body, data)

    raw = json.loads(data.decode("utf-8", errors="replace"))
    body = raw.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("JSON response body not found")

    return {
        "error": body.get("error", -1),
        "raw": raw,
    }


def _post_cgi_xml(
    xml_body: bytes,
    *,
    host: str,
    port: int,
    scheme: str,
    debug: bool,
    verify_tls: bool,
) -> bytes:
    req = urllib.request.Request(
        f"{scheme}://{host}:{port}/tdkcgi",
        data=xml_body,
        headers={"Content-Type": "application/xml"},
        method="POST",
    )

    context = None
    if scheme == "https":
        context = (
            ssl.create_default_context()
            if verify_tls
            else ssl._create_unverified_context()
        )

    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:
            return cast(bytes, resp.read())
    except urllib.error.HTTPError as exc:
        data = exc.read()
        if debug:
            logger.debug("HTTP status: {}", exc.code)
            _debug_exchange(xml_body, data)
        raise
    except Exception:
        if debug:
            logger.debug(
                "Request XML:\n{}",
                redaction.redact_xml_text(
                    xml_body.decode("utf-8", errors="replace")
                ),
            )
        raise


def _post_cgi_json(
    json_body: bytes,
    *,
    host: str,
    port: int,
    scheme: str,
    debug: bool,
    verify_tls: bool,
) -> bytes:
    req = urllib.request.Request(
        f"{scheme}://{host}:{port}/tdkcgi",
        data=json_body,
        headers={"Content-Type": 'application/json; charset="UTF-8"'},
        method="POST",
    )

    context = None
    if scheme == "https":
        context = (
            ssl.create_default_context()
            if verify_tls
            else ssl._create_unverified_context()
        )

    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:
            return cast(bytes, resp.read())
    except urllib.error.HTTPError as exc:
        data = exc.read()
        if debug:
            logger.debug("HTTP status: {}", exc.code)
            _debug_json_exchange(json_body, data)
        raise
    except Exception:
        if debug:
            logger.debug(
                "Request JSON:\n{}",
                redaction.redact_json_text(
                    json_body.decode("utf-8", errors="replace")
                ),
            )
        raise


def _debug_exchange(xml_body: bytes, data: bytes) -> None:
    logger.debug(
        "Request XML:\n{}",
        redaction.redact_xml_text(xml_body.decode("utf-8", errors="replace")),
    )
    logger.debug(
        "Raw response:\n{}",
        redaction.redact_xml_text(data.decode("utf-8", errors="replace")),
    )


def _debug_json_exchange(json_body: bytes, data: bytes) -> None:
    logger.debug(
        "Request JSON:\n{}",
        redaction.redact_json_text(
            json_body.decode("utf-8", errors="replace")
        ),
    )
    logger.debug(
        "Raw response:\n{}",
        redaction.redact_json_text(data.decode("utf-8", errors="replace")),
    )

import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, cast

from quii_helper.cloud.config.defaults import CLOUD_COOKIE, CLOUD_COOKIE_JAR
from quii_helper.support import redaction
from quii_helper.support.log import logger


def build_cloud_opener(
    *, verify_tls: bool = True
) -> urllib.request.OpenerDirector:
    context = (
        ssl.create_default_context()
        if verify_tls
        else ssl._create_unverified_context()
    )
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CLOUD_COOKIE_JAR),
        urllib.request.HTTPSHandler(context=context),
    )


def dump_cookie_jar(*, redact: bool = True) -> list[str]:
    cookies = []
    for cookie in CLOUD_COOKIE_JAR:
        value = redaction.REDACTED if redact else cookie.value
        cookies.append(f"{cookie.name}={value}")
    return cookies


def request_userauth(
    xml_body: bytes,
    *,
    auth_url: str,
    debug: bool = False,
    verify_tls: bool = True,
) -> tuple[ET.Element, str]:
    headers = {
        "Content-Type": "application/xml",
        "Charset": "utf-8",
        "Accept-Language": "en-US",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "okhttp/3.12.13",
        "Connection": "close",
    }
    if CLOUD_COOKIE:
        headers["Cookie"] = CLOUD_COOKIE

    req = urllib.request.Request(
        auth_url,
        data=xml_body,
        headers=headers,
        method="POST",
    )

    opener = build_cloud_opener(verify_tls=verify_tls)

    try:
        with opener.open(req, timeout=15) as resp:
            data = cast(bytes, resp.read())
            response_headers = dict(resp.info())
    except urllib.error.HTTPError as exc:
        data = exc.read()
        response_headers = dict(exc.headers.items())
        if debug:
            _debug_userauth_exchange(
                req, xml_body, data, response_headers, status_code=exc.code
            )
        raise

    if debug:
        _debug_userauth_exchange(req, xml_body, data, response_headers)

    root = ET.fromstring(data)
    return root, data.decode("utf-8", errors="replace")


def _debug_userauth_exchange(
    req: urllib.request.Request,
    xml_body: bytes,
    response_data: bytes,
    response_headers: dict[str, Any],
    *,
    status_code: int | None = None,
) -> None:
    if status_code is not None:
        logger.debug("HTTP status: {}", status_code)
    logger.debug("Request URL: {}", req.full_url)
    logger.debug(
        "Request headers: {}",
        redaction.redact_mapping(dict(req.header_items())),
    )
    logger.debug("Cookie jar: {}", dump_cookie_jar())
    logger.debug(
        "Response headers: {}", redaction.redact_mapping(response_headers)
    )
    logger.debug(
        "Request XML:\n{}",
        redaction.redact_xml_text(xml_body.decode("utf-8", errors="replace")),
    )
    logger.debug(
        "Raw response:\n{}",
        redaction.redact_xml_text(
            response_data.decode("utf-8", errors="replace")
        ),
    )

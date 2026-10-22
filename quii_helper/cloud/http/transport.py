import gzip
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from http.cookiejar import CookieJar
from typing import Any, cast

from quii_helper.support import redaction
from quii_helper.support.errors import QuiiConnectionError
from quii_helper.support.log import logger


def build_cloud_opener(
    *, verify_tls: bool = True, cookie_jar: CookieJar | None = None
) -> urllib.request.OpenerDirector:
    context = (
        ssl.create_default_context()
        if verify_tls
        else ssl._create_unverified_context()
    )
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(
            CookieJar() if cookie_jar is None else cookie_jar
        ),
        urllib.request.HTTPSHandler(context=context),
    )


def dump_cookie_jar(
    *, redact: bool = True, cookie_jar: CookieJar | None = None
) -> list[str]:
    cookies = []
    for cookie in () if cookie_jar is None else cookie_jar:
        value = redaction.REDACTED if redact else cookie.value
        cookies.append(f"{cookie.name}={value}")
    return cookies


def request_userauth(
    xml_body: bytes,
    *,
    auth_url: str,
    debug: bool = False,
    verify_tls: bool = True,
    cookie_jar: CookieJar | None = None,
) -> tuple[ET.Element, str]:
    """Post XML with optional cookie isolation for a separate cloud service."""
    headers = {
        "Content-Type": "application/xml",
        "Charset": "utf-8",
        "Accept-Language": "en-US",
        "Accept-Encoding": "gzip",
        "User-Agent": "okhttp/3.12.13",
        "Connection": "close",
    }
    if cookie_jar is None:
        cookie_jar = CookieJar()

    req = urllib.request.Request(
        auth_url,
        data=xml_body,
        headers=headers,
        method="POST",
    )

    opener = build_cloud_opener(verify_tls=verify_tls, cookie_jar=cookie_jar)

    try:
        with opener.open(req, timeout=15) as resp:
            data = cast(bytes, resp.read())
            response_headers = {
                key.lower(): value for key, value in resp.info().items()
            }
            status_code = resp.status
    except urllib.error.HTTPError as exc:
        data = exc.read()
        response_headers = {
            key.lower(): value for key, value in exc.headers.items()
        }
        if debug:
            try:
                data = _decode_cloud_body(data, response_headers)
            except QuiiConnectionError:
                data = b""
            _debug_userauth_exchange(
                req,
                xml_body,
                data,
                response_headers,
                status_code=exc.code,
                cookie_jar=cookie_jar,
            )
        raise

    data = _decode_cloud_body(data, response_headers)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise QuiiConnectionError(
            "cloud HTTP response is not valid XML; "
            f"status={status_code}; "
            f"content_type={response_headers.get('content-type', 'unknown')!r}; "
            f"content_encoding="
            f"{response_headers.get('content-encoding', 'identity')!r}; "
            f"body_bytes={len(data)}"
        ) from exc

    if debug:
        _debug_userauth_exchange(
            req,
            xml_body,
            data,
            response_headers,
            status_code=status_code,
            cookie_jar=cookie_jar,
        )

    return root, data.decode("utf-8", errors="replace")


def _decode_cloud_body(data: bytes, headers: dict[str, str]) -> bytes:
    """Match OkHttp's gzip negotiation before parsing or logging XML."""
    encoding = headers.get("content-encoding", "").strip().lower()
    if encoding in ("", "identity"):
        return data
    if encoding != "gzip":
        raise QuiiConnectionError(
            f"unsupported cloud HTTP Content-Encoding: {encoding!r}; "
            "only gzip or identity was requested"
        )
    try:
        return gzip.decompress(data)
    except (OSError, EOFError, zlib.error):
        raise QuiiConnectionError(
            "invalid gzip-compressed cloud HTTP response"
        ) from None


def _debug_userauth_exchange(
    req: urllib.request.Request,
    xml_body: bytes,
    response_data: bytes,
    response_headers: dict[str, Any],
    *,
    status_code: int | None = None,
    cookie_jar: CookieJar | None = None,
) -> None:
    if status_code is not None:
        logger.debug("HTTP status: {}", status_code)
    logger.debug("Request URL: {}", req.full_url)
    logger.debug(
        "Request headers: {}",
        redaction.redact_mapping(dict(req.header_items())),
    )
    logger.debug("Cookie jar: {}", dump_cookie_jar(cookie_jar=cookie_jar))
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

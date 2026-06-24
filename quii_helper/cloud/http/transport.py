import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from quii_helper.cloud.config.defaults import CLOUD_COOKIE, CLOUD_COOKIE_JAR
from quii_helper.support.log import logger


def build_cloud_opener():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CLOUD_COOKIE_JAR),
        urllib.request.HTTPSHandler(context=context),
    )


def dump_cookie_jar():
    cookies = []
    for cookie in CLOUD_COOKIE_JAR:
        cookies.append(f"{cookie.name}={cookie.value}")
    return cookies


def request_userauth(xml_body: bytes, *, auth_url: str, debug: bool = False):
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

    opener = build_cloud_opener()

    try:
        with opener.open(req, timeout=15) as resp:
            data = resp.read()
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
    response_headers: dict,
    *,
    status_code: int | None = None,
) -> None:
    if status_code is not None:
        logger.debug("HTTP status: {}", status_code)
    logger.debug("Request URL: {}", req.full_url)
    logger.debug("Request headers: {}", dict(req.header_items()))
    logger.debug("Cookie jar: {}", dump_cookie_jar())
    logger.debug("Response headers: {}", response_headers)
    logger.debug(
        "Request XML:\n{}", xml_body.decode("utf-8", errors="replace")
    )
    logger.debug(
        "Raw response:\n{}", response_data.decode("utf-8", errors="replace")
    )

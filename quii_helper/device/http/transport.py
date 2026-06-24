import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from quii_helper.device.http.xml import build_request_xml
from quii_helper.device.security.auth import get_encrypt_password
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
    debug: bool = False,
):
    if encrypted:
        security = "usernametoken"
        request_password = get_encrypt_password(username, password, nc)
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
    )
    data = _post_cgi_xml(
        xml_body,
        host=host,
        port=port,
        scheme=scheme,
        debug=debug,
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


def _post_cgi_xml(
    xml_body: bytes,
    *,
    host: str,
    port: int,
    scheme: str,
    debug: bool,
) -> bytes:
    req = urllib.request.Request(
        f"{scheme}://{host}:{port}/tdkcgi",
        data=xml_body,
        headers={"Content-Type": "application/xml"},
        method="POST",
    )

    context = None
    if scheme == "https":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:
            return resp.read()
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
                xml_body.decode("utf-8", errors="replace"),
            )
        raise


def _debug_exchange(xml_body: bytes, data: bytes) -> None:
    logger.debug(
        "Request XML:\n{}", xml_body.decode("utf-8", errors="replace")
    )
    logger.debug("Raw response:\n{}", data.decode("utf-8", errors="replace"))

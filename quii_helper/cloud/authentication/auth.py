import xml.etree.ElementTree as ET

from quii_helper.cloud.authentication.responses import (
    parse_device_token_response,
    parse_login_response,
)
from quii_helper.cloud.config.defaults import (
    CLOUD_LOGIN_SEQ,
    DEVICE_TOKEN_REQ_CLASS,
    LOGIN_REQ_CLASS,
)
from quii_helper.cloud.http.transport import request_userauth
from quii_helper.cloud.http.xml import build_userauth_xml, userauth_password
from quii_helper.support.errors import ConfigurationError


def login_cloud(
    account: str,
    password: str,
    *,
    auth_url: str,
    ip_region_id: int,
    client_id: str,
    oem: str,
    app_id: int,
    client_type: int,
    debug: bool = False,
    verify_tls: bool = True,
) -> dict[str, str]:
    _validate_userauth_identity(
        client_id=client_id,
        oem=oem,
        app_id=app_id,
        client_type=client_type,
        ip_region_id=ip_region_id,
    )
    hashed_password = userauth_password(password)

    def content_builder(content: ET.Element) -> None:
        ET.SubElement(content, "account").text = account
        ET.SubElement(content, "auth-code").text = ""
        ET.SubElement(content, "ip-region-id").text = str(ip_region_id)
        ET.SubElement(content, "password").text = hashed_password
        ET.SubElement(content, "auth-type").text = "0"

    xml_body = build_userauth_xml(
        "login",
        content_builder,
        content_class=LOGIN_REQ_CLASS,
        session_id=None,
        seq=CLOUD_LOGIN_SEQ,
        client_id=client_id,
        oem=oem,
        app_id=app_id,
        client_type=client_type,
    )
    root, raw = request_userauth(
        xml_body,
        auth_url=auth_url,
        debug=debug,
        verify_tls=verify_tls,
    )
    return parse_login_response(root, raw)


def get_device_token(
    session_id: str,
    device_id: str,
    *,
    auth_url: str,
    client_id: str,
    oem: str,
    app_id: int,
    client_type: int,
    is_hs_device: object | None = None,
    debug: bool = False,
    verify_tls: bool = True,
) -> dict[str, str]:
    _validate_userauth_identity(
        client_id=client_id,
        oem=oem,
        app_id=app_id,
        client_type=client_type,
    )

    def content_builder(content: ET.Element) -> None:
        ET.SubElement(content, "device-id").text = device_id
        if is_hs_device is not None:
            ET.SubElement(content, "is-hs-device").text = str(is_hs_device)

    xml_body = build_userauth_xml(
        "get-device-token",
        content_builder,
        content_class=DEVICE_TOKEN_REQ_CLASS,
        session_id=session_id,
        seq=0,
        client_id=client_id,
        oem=oem,
        app_id=app_id,
        client_type=client_type,
    )
    root, raw = request_userauth(
        xml_body,
        auth_url=auth_url,
        debug=debug,
        verify_tls=verify_tls,
    )
    return parse_device_token_response(root, raw)


def _validate_userauth_identity(
    *,
    client_id: str,
    oem: str,
    app_id: int,
    client_type: int,
    ip_region_id: int | None = None,
) -> None:
    missing = []
    if not client_id:
        missing.append("client_id")
    if not oem:
        missing.append("oem")
    if app_id <= 0:
        missing.append("app_id")
    if client_type <= 0:
        missing.append("client_type")
    if ip_region_id is not None and ip_region_id <= 0:
        missing.append("ip_region_id")
    if missing:
        raise ConfigurationError(
            "missing required userauth identity values: "
            f"{', '.join(missing)}"
        )

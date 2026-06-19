import xml.etree.ElementTree as ET

from quii_helper.cloud.defaults import (
    CLOUD_LOGIN_SEQ,
    DEVICE_TOKEN_REQ_CLASS,
    LOGIN_REQ_CLASS,
)
from quii_helper.cloud.transport import request_userauth
from quii_helper.cloud.xml import build_userauth_xml, userauth_password


def login_cloud(
    account: str,
    password: str,
    *,
    ip_region_id: int = 6,
    client_id: str | None = None,
    debug: bool = False,
):
    hashed_password = userauth_password(password)

    def content_builder(content: ET.Element):
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
    )
    root, raw = request_userauth(xml_body, debug=debug)

    header = root.find("./header")
    if header is None:
        raise RuntimeError("login response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise RuntimeError(f"cloud login result: {result}")

    session_id = (
        header.findtext("./session/id") or header.findtext("session") or ""
    ).strip()
    account_id = (root.findtext("./content/account-id") or "").strip()
    token = (root.findtext("./content/token") or "").strip()
    expire = (root.findtext("./content/expire") or "").strip()

    return {
        "session_id": session_id,
        "account_id": account_id,
        "token": token,
        "expire": expire,
        "raw": raw,
    }


def get_device_token(
    session_id: str,
    device_id: str,
    *,
    is_hs_device=None,
    client_id: str | None = None,
    debug: bool = False,
):
    def content_builder(content: ET.Element):
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
    )
    root, raw = request_userauth(xml_body, debug=debug)

    header = root.find("./header")
    if header is None:
        raise RuntimeError("device-token response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise RuntimeError(f"device-token result: {result}")

    content = root.find("./content")
    if content is None:
        raise RuntimeError("device-token response content not found")

    return {
        "device_id": (
            content.findtext("deviceid") or content.findtext("device-id") or ""
        ).strip(),
        "data_encode_key": (
            content.findtext("dataEncodeKey")
            or content.findtext("data-encode-key")
            or ""
        ).strip(),
        "dynamic_password": (
            content.findtext("dynamicPassword")
            or content.findtext("dynamic-password")
            or ""
        ).strip(),
        "pwd_expired": (
            content.findtext("pwdExpired")
            or content.findtext("password-expired")
            or ""
        ).strip(),
        "transparent_basedata": (
            content.findtext("transparentBasedata")
            or content.findtext("transparent-basedata")
            or ""
        ).strip(),
        "auth_code": (
            content.findtext("authCode")
            or content.findtext("out-auth-code")
            or content.findtext("auth-code")
            or ""
        ).strip(),
        "default_out_auth_code": (
            content.findtext("defaultOutAuthCode")
            or content.findtext("default-out-auth-code")
            or ""
        ).strip(),
        "raw": raw,
    }

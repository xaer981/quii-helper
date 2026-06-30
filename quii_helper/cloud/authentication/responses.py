import xml.etree.ElementTree as ET

from quii_helper.support.errors import QuiiConnectionError


def parse_login_response(root: ET.Element, raw: str) -> dict[str, str]:
    header = root.find("./header")
    if header is None:
        raise QuiiConnectionError("login response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise QuiiConnectionError(f"cloud login result: {result}")

    session_id = (
        header.findtext("./session/id") or header.findtext("session") or ""
    ).strip()
    return {
        "session_id": session_id,
        "account_id": (root.findtext("./content/account-id") or "").strip(),
        "token": (root.findtext("./content/token") or "").strip(),
        "expire": (root.findtext("./content/expire") or "").strip(),
        "raw": raw,
    }


def parse_device_token_response(root: ET.Element, raw: str) -> dict[str, str]:
    header = root.find("./header")
    if header is None:
        raise QuiiConnectionError("device-token response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise QuiiConnectionError(f"device-token result: {result}")

    content = root.find("./content")
    if content is None:
        raise QuiiConnectionError("device-token response content not found")

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

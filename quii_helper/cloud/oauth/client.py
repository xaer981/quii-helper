import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from quii_helper.cloud.http.xml import userauth_password
from quii_helper.cloud.oauth.models import CloudOAuthToken
from quii_helper.config import AutonomousConfig
from quii_helper.support.errors import QuiiConnectionError

OAUTH_TOKEN_PATH = "/qvoauthv2/token"


def alarm_client_id(config: AutonomousConfig) -> str:
    """Return native `SDKVariates.ALARM_CLIENT_ID` for OAuth/OpenAPI calls."""

    return f"00{config.client_type}-{config.app_id}-{config.client_id}"


def build_oauth_token_query(config: AutonomousConfig) -> dict[str, str]:
    """Build the native `QvOAuthManager.getToken()` query map."""

    return {
        "grant_type": "password",
        "client_id": alarm_client_id(config),
        "client_type": str(config.client_type),
        "oemid": config.oem,
        "appid": str(config.app_id),
        "usr": config.cloud_account,
        "pwd": userauth_password(config.cloud_password),
        "region_id": str(config.ip_region_id),
        "client_flag": "1",
    }


def request_oauth_token(
    base_url: str,
    config: AutonomousConfig,
    *,
    timeout: float,
    verify_tls: bool,
) -> CloudOAuthToken:
    """Request an OAuth access token using the native GET `/qvoauthv2/token`.

    The original Android client uses Retrofit `@GET` with `@QueryMap`; using
    query parameters here is intentional and avoids changing server behavior.
    """

    query = urllib.parse.urlencode(build_oauth_token_query(config))
    url = f"{base_url.rstrip('/')}{OAUTH_TOKEN_PATH}?{query}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "okhttp/3.12.13",
        },
    )
    context = (
        ssl.create_default_context()
        if verify_tls
        else ssl._create_unverified_context()
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=context
        ) as response:
            response_bytes = cast(bytes, response.read())
    except urllib.error.URLError as exc:
        raise QuiiConnectionError(
            f"OAuth token request failed: {exc}"
        ) from exc

    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise QuiiConnectionError("OAuth token response is not JSON") from exc

    if not isinstance(payload, dict):
        raise QuiiConnectionError("OAuth token response is not an object")
    return parse_oauth_token(cast(dict[str, Any], payload))


def parse_oauth_token(payload: dict[str, Any]) -> CloudOAuthToken:
    """Parse the vendor OAuth token response."""

    access_token = str(payload.get("access_token") or "")
    refresh_token = str(payload.get("refresh_token") or "")
    if not access_token:
        code = payload.get("code", payload.get("result", ""))
        message = payload.get("message", payload.get("msg", ""))
        suffix = f": {code} {message}".strip() if code or message else ""
        raise QuiiConnectionError(
            f"OAuth token response has no access_token{suffix}"
        )
    return CloudOAuthToken(
        access_token=access_token,
        refresh_token=refresh_token,
        raw=payload,
    )

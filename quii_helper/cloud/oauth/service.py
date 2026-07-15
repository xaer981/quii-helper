from urllib.parse import urlparse

from quii_helper.cloud.oauth.client import request_oauth_token
from quii_helper.cloud.oauth.models import CloudOAuthToken
from quii_helper.cloud.services.discovery import query_service_addresses
from quii_helper.config import AutonomousConfig, ServiceEntry
from quii_helper.support.errors import QuiiConnectionError

OAUTH_SERVICE_TYPES = ("oauth", "qvoauth", "auth", "userauth")


def fetch_oauth_access_token(config: AutonomousConfig) -> CloudOAuthToken:
    """Fetch a cloud OAuth token for OpenAPI, shadow, and IoT requests."""

    service_url = resolve_oauth_service_url(config)
    return request_oauth_token(
        service_url,
        config,
        timeout=config.connect_timeout,
        verify_tls=config.tls_verify,
    )


def resolve_oauth_service_url(config: AutonomousConfig) -> str:
    """Resolve native service type 4 base URL, falling back to auth host."""

    try:
        response = query_service_addresses(
            config, server_types=OAUTH_SERVICE_TYPES
        )
    except QuiiConnectionError:
        return _auth_origin_url(config.auth_url)

    for service_type in OAUTH_SERVICE_TYPES:
        entry = response.find(service_type)
        if entry is not None and entry.url:
            return _entry_base_url(entry)
    return _auth_origin_url(config.auth_url)


def _entry_base_url(entry: ServiceEntry) -> str:
    base = entry.url.rstrip("/")
    uri = entry.uri.strip("/")
    return f"{base}/{uri}" if uri else base


def _auth_origin_url(auth_url: str) -> str:
    parsed = urlparse(auth_url)
    if not parsed.scheme or not parsed.netloc:
        raise QuiiConnectionError("CLOUD_AUTH_URL cannot be used for OAuth")
    return f"{parsed.scheme}://{parsed.netloc}"

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudOAuthToken:
    """OAuth token returned by the vendor `/qvoauthv2/token` endpoint."""

    access_token: str
    refresh_token: str
    raw: dict[str, object]

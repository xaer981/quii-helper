"""Discover cloud region and service endpoints for `.env`.

Fill the APK-derived values in `.env` first:

- CLOUD_SERVICE_URL
- CAMERA_OEM
- CLOUD_CLIENT_UUID

The script uses the same mTLS service-discovery request as the native P2P SDK.
It does not need the cloud account password.
"""

from __future__ import annotations

from urllib.parse import urljoin

from quii_helper.cloud.services.discovery import query_service_addresses
from quii_helper.config import AutonomousConfig

USERAUTH_PATH = "/auth/user"
SERVER_TYPES = ("userapp", "p2papp", "natcheck", "appinfo")


def main() -> None:
    """Print discovered values that can be copied into `.env`."""
    config = AutonomousConfig(ip_region_id=0, tls_verify=False)
    response = query_service_addresses(config, server_types=SERVER_TYPES)

    print(f"IP_REGION_ID={response.client_region_id}")

    userapp = response.find("userapp")
    if userapp and userapp.url:
        print(f"CLOUD_AUTH_URL={urljoin(userapp.url, USERAUTH_PATH)}")
    else:
        print("# CLOUD_AUTH_URL was not returned as userapp service.")

    print("\n# Raw discovered services:")
    for entry in response.servers:
        print(
            f"{entry.server_type}: region={entry.region_id} "
            f"url={entry.url} uri={entry.uri} param={entry.param}"
        )


if __name__ == "__main__":
    main()

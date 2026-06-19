from quii_helper.device.cgi import encode_device_password
from quii_helper.protocols.tcp import settings


def status_probe_kwargs() -> dict:
    return {
        "host": settings.HOST,
        "port": 80,
        "username": "adminapp2",
        "password": encode_device_password(settings.AUTH_CODE),
        "encrypted": False,
        "scheme": "http",
        "passwordencode": "1",
    }


def primary_streamkey_mode() -> tuple[str, dict]:
    return (
        "lan_authcode_http",
        {
            "host": settings.HOST,
            "port": 80,
            "username": "adminapp2",
            "password": encode_device_password(settings.AUTH_CODE),
            "encrypted": False,
            "scheme": "http",
            "passwordencode": "1",
        },
    )


def fallback_streamkey_modes() -> list[tuple[str, dict]]:
    return [
        (
            "lan_authcode_http_no_flag",
            {
                "host": settings.HOST,
                "port": 80,
                "username": "adminapp2",
                "password": encode_device_password(settings.AUTH_CODE),
                "encrypted": False,
                "scheme": "http",
                "passwordencode": None,
            },
        ),
        (
            "lan_authcode_http_raw",
            {
                "host": settings.HOST,
                "port": 80,
                "username": "adminapp2",
                "password": settings.AUTH_CODE,
                "encrypted": False,
                "scheme": "http",
                "passwordencode": None,
            },
        ),
        (
            "device_plain_http",
            {
                "host": settings.HOST,
                "port": 80,
                "username": "adminapp",
                "password": settings.DEVICE_PASSWORD,
                "encrypted": False,
                "scheme": "http",
                "passwordencode": None,
            },
        ),
        (
            "device_plain_http_encoded",
            {
                "host": settings.HOST,
                "port": 80,
                "username": "adminapp",
                "password": settings.DEVICE_PASSWORD,
                "encrypted": False,
                "scheme": "http",
                "passwordencode": "1",
            },
        ),
        (
            "device_plain_http_hashed",
            {
                "host": settings.HOST,
                "port": 80,
                "username": "adminapp",
                "password": encode_device_password(settings.DEVICE_PASSWORD),
                "encrypted": False,
                "scheme": "http",
                "passwordencode": "1",
            },
        ),
        (
            "device_token_https",
            {
                "host": settings.HOST,
                "port": 443,
                "username": "adminapp",
                "password": settings.DEVICE_PASSWORD,
                "encrypted": True,
                "nc": settings.NC,
                "scheme": "https",
                "passwordencode": None,
            },
        ),
        (
            "lan_token_https",
            {
                "host": settings.HOST,
                "port": 443,
                "username": "adminapp2",
                "password": settings.DEVICE_PASSWORD,
                "encrypted": True,
                "nc": settings.NC,
                "scheme": "https",
                "passwordencode": None,
            },
        ),
    ]

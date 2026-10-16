"""Print capability 24 and send one real door-opening command in auto mode."""

from quii_helper import Camera


def main() -> None:
    """Open the configured door once using environment-backed settings."""
    camera = Camera()
    info = camera.get_device_info()
    print(
        f"Capability 24 (TYPE_ENCRYPY_SHA256): {info.supports_sha256_password}",
        flush=True,
    )
    result = camera.open_door(password_mode="auto")
    print(result, flush=True)
    print(
        f"Accepted: {result.accepted}; message: {result.message}", flush=True
    )


if __name__ == "__main__":
    main()

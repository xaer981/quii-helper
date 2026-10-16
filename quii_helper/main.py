from quii_helper import Camera


def main() -> None:
    """Print capability 24 and send one real door-open command in auto mode."""

    camera = Camera(stream_quality="high", live_newcn=True, tls_verify=False)
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
    try:
        main()
    except KeyboardInterrupt:
        pass

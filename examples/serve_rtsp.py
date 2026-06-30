"""Serve the camera preview as RTSP until interrupted."""

from quii_helper import Camera


def main() -> None:
    """Start RTSP serving with environment-backed settings."""
    camera = Camera()
    with camera.serve_rtsp(port=8554) as stream:
        stream.wait()


if __name__ == "__main__":
    main()

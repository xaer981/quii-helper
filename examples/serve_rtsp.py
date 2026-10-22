"""Serve the camera preview as RTSP until interrupted."""

from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Start RTSP serving with environment-backed settings."""
    configure_logging(replace_existing=True)
    camera = Camera(config=load_config())
    with camera.serve_rtsp(port=8554) as stream:
        stream.wait()


if __name__ == "__main__":
    main()

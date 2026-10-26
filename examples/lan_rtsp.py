"""Serve LAN-only RTSP with saved credentials, without cloud access.

Run ``python -m examples.lan_rtsp`` from the checkout root. Set the camera IP,
channel and stream in `.env` (CAMERA_STREAM accepts "high", "low", or numeric
ids); first save `data/stream_credentials.json` using
the explicit cloud bootstrap API/example. No key refresh is attempted here.
"""

from quii_helper import Camera, CameraStreamCredentials, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Load the key/auth pair and serve local RTSP until interrupted.

    Missing/invalid credentials and producer errors propagate to the caller;
    neither cloud login nor a door command is sent.
    """
    configure_logging(replace_existing=True)
    config = load_config()
    saved = CameraStreamCredentials.load("data/stream_credentials.json")
    camera = Camera(
        config=config,
        connection_mode="lan",
        device_id=saved.device_id,
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    try:
        with camera.serve_rtsp(port=8554) as stream:
            stream.wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

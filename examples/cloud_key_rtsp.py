"""Explicit cloud key bootstrap, followed by RTSP from a LAN-only Camera.

Run ``python -m examples.cloud_key_rtsp`` with cloud/app settings and the LAN IP
configured in `.env`. Every run fetches and replaces the saved pair. Use
``python -m examples.lan_rtsp`` for subsequent starts without cloud requests.
The later LAN preview honors CAMERA_CHANNEL and CAMERA_STREAM ("high", "low",
or a numeric id); cloud bootstrap does not choose a panel or quality profile.
"""

from quii_helper import Camera, CameraStreamCredentials, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Fetch/save credentials, reload them, then serve LAN RTSP until Ctrl+C.

    Running this example always contacts cloud first. It honors TLS_VERIFY and
    never opens a door. Later offline runs can load the JSON directly instead.
    """
    configure_logging(replace_existing=True)
    config = load_config()
    cloud_camera = Camera(config=config, connection_mode="cloud")
    credentials = cloud_camera.fetch_stream_credentials()
    saved_path = credentials.save(
        cloud_camera.data_dir / "stream_credentials.json"
    )
    print(f"Streaming credentials saved: {saved_path}")

    saved = CameraStreamCredentials.load(saved_path)
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

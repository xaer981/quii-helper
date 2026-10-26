from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Serve the camera preview over RTSP until interrupted."""

    configure_logging(replace_existing=True)
    camera = Camera(
        config=load_config(),
        tls_verify=False,
    )
    with camera.serve_rtsp(port=8554, audio=True) as stream:
        stream.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

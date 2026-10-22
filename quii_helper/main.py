from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Serve the camera preview over RTSP until interrupted."""

    configure_logging(replace_existing=True)
    camera = Camera(
        config=load_config(),
        stream_quality="high",
        live_newcn=True,
        tls_verify=False,
    )
    with camera.serve_rtsp(port=8554) as stream:
        stream.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

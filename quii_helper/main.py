import time

from quii_helper import Camera


def main() -> None:
    """Run a simple RTSP preview server example."""

    camera = Camera(stream_quality="high", live_newcn=True, tls_verify=False)
    with camera.serve_rtsp(port=8554):
        while True:
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

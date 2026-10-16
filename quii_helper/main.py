from quii_helper import Camera


def main() -> None:
    """Serve the camera preview over RTSP until interrupted."""

    camera = Camera(stream_quality="high", live_newcn=True, tls_verify=False)
    with camera.serve_rtsp(port=8554) as stream:
        stream.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

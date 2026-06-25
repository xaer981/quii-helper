import time

from quii_helper import Camera

try:
    camera = Camera(stream_quality="high", live_newcn=True)
    with camera.serve_rtsp(port=8554) as stream:
        print(f"RTSP URL: {stream.url}")

        while True:
            time.sleep(1)
except KeyboardInterrupt:
    pass

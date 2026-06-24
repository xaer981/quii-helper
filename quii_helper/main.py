from quii_helper import Camera

camera = Camera(stream_quality="high", live_newcn=True)

result = camera.capture(
    duration_seconds=15,
    render_snapshot=False,
    render_video=True,
    stop_when_decodable=False,
)

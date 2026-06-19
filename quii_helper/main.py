from quii_helper import Camera

camera = Camera()

result = camera.capture(
    duration_seconds=60,
    render_snapshot=False,
    render_video=True,
    stop_when_decodable=False,
)

print(result.summary)

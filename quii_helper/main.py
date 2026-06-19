from quii_helper import Camera


def compact_summary(summary: dict) -> dict:
    result = dict(summary)
    media_result = result.get("media_result")
    if isinstance(media_result, dict):
        compact_media_result = dict(media_result)
        frames = compact_media_result.pop("frames", [])
        compact_media_result["frames_count"] = (
            len(frames) if isinstance(frames, list) else 0
        )
        result["media_result"] = compact_media_result
    return result


camera = Camera(stream_quality="high", live_newcn=True)

result = camera.capture(
    duration_seconds=15,
    render_snapshot=False,
    render_video=True,
    stop_when_decodable=False,
)

print(compact_summary(result.summary))

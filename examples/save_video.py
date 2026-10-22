"""Record a short MP4 clip using environment-backed settings."""

from pathlib import Path

from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main(duration_seconds: float = 30.0) -> Path:
    """Capture a video clip and print the written path."""
    configure_logging(replace_existing=True)
    camera = Camera(config=load_config())
    path = camera.save_video(duration_seconds=duration_seconds)
    print(path)
    return path


if __name__ == "__main__":
    main()

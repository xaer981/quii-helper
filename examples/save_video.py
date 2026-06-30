"""Record a short MP4 clip using environment-backed settings."""

from pathlib import Path

from quii_helper import Camera


def main(duration_seconds: float = 30.0) -> Path:
    """Capture a video clip and print the written path."""
    camera = Camera()
    path = camera.save_video(duration_seconds=duration_seconds)
    print(path)
    return path


if __name__ == "__main__":
    main()

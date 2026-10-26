"""Capture a JPEG using CAMERA_CHANNEL and CAMERA_STREAM from .env.

CAMERA_STREAM accepts "high", "low", or numeric ids; quality is not overridden.
"""

from pathlib import Path

from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main() -> Path:
    """Capture one snapshot and print the written path."""
    configure_logging(replace_existing=True)
    camera = Camera(config=load_config())
    path = camera.snapshot(timeout_seconds=10)
    print(path)
    return path


if __name__ == "__main__":
    main()

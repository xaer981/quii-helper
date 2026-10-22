"""Capture a single JPEG snapshot using environment-backed settings."""

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

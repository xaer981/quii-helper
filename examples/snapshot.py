"""Capture a single JPEG snapshot using environment-backed settings."""

from pathlib import Path

from quii_helper import Camera


def main() -> Path:
    """Capture one snapshot and print the written path."""
    camera = Camera()
    path = camera.snapshot(timeout_seconds=10)
    print(path)
    return path


if __name__ == "__main__":
    main()

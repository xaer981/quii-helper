"""Camera streaming entrypoints."""

from quii_helper.camera.streaming.audio import CameraAudioStream
from quii_helper.camera.streaming.rtsp import CameraRtspStream

__all__ = ["CameraAudioStream", "CameraRtspStream"]

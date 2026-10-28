"""Explicitly send data/talk.wav to the intercom speaker over LAN.

Run ``python -m examples.talk`` only when it is safe to activate talk. Unlike
listen_audio, this is NOT a read-only probe: it reserves a talk connection and
transmits sound. Supply an uncompressed PCM16 LE, 8000 Hz mono WAV. Saved
credentials and local settings are used. CAMERA_CHANNEL selects the preview
panel, CAMERA_STREAM its quality; talk uses generic selector 65535. Preview
audio must become available before transmission. No cloud, microphone or door command.
"""

import wave
from pathlib import Path

from quii_helper import Camera, CameraStreamCredentials, load_config
from quii_helper.support.log import configure_logging


def send_wav(camera: Camera, path: Path) -> None:
    """Send at most one second per batch; pad the final block with silence."""
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != 8000
            or source.getcomptype() != "NONE"
        ):
            raise ValueError(
                "talk WAV must be uncompressed PCM16 LE, 8000 Hz mono"
            )
        if source.getnframes() == 0:
            raise ValueError("talk WAV must not be empty")
        with camera.talk() as talk:
            while pcm := source.readframes(8000):
                # The core API never pads: this example explicitly adds <40ms silence.
                pcm += bytes(-len(pcm) % 640)
                talk.send_pcm(pcm)


def main() -> None:
    """Play a user-prepared WAV, never run automatically from the default main."""
    configure_logging(replace_existing=True)
    saved = CameraStreamCredentials.load("data/stream_credentials.json")
    camera = Camera(
        config=load_config(),
        connection_mode="lan",
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    try:
        send_wav(camera, Path("data/talk.wav"))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

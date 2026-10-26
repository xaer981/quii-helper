"""Inspect ten LAN audio frames using saved credentials; never transmit audio.

Run ``python -m examples.listen_audio`` from the checkout root. Configure the
camera IP/channel/stream in `.env` and save `data/stream_credentials.json` via
the explicit cloud bootstrap first. CAMERA_STREAM accepts "high", "low", or numeric
ids; this example does not override it. The key is never refreshed here.
It prints metadata only: no microphone, speaker, recording or door command.
"""

from quii_helper import Camera, CameraStreamCredentials, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Read ten encoded frames; timeout/errors propagate and close the socket."""
    configure_logging(replace_existing=True)
    saved = CameraStreamCredentials.load("data/stream_credentials.json")
    camera = Camera(
        config=load_config(),
        connection_mode="lan",
        device_id=saved.device_id,
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    try:
        with camera.listen_audio() as audio:
            for index in range(1, 11):
                frame = audio.recv_frame(timeout=5.0)
                print(
                    f"frame={index} codec={frame.codec_name} "
                    f"sample_rate={frame.sample_rate} channels={frame.channels} "
                    f"bytes={len(frame.data)} frame_stamp={frame.frame_stamp} "
                    f"milliseconds={frame.milliseconds}"
                )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

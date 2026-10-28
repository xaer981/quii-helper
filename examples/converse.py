"""Watch RTSP, then explicitly toggle PC conversation on the same preview.

Install the audio extra first. Use --list-devices before selecting exact names.
Run only when it is safe to activate the panel speaker. Ctrl+C stops both
directions. OS microphone permission is required; headphones avoid feedback.
"""

import argparse
import math

from quii_helper import Camera, CameraStreamCredentials, load_config
from quii_helper.media.audio.devices import list_audio_devices
from quii_helper.support.log import configure_logging


def main() -> None:
    """Use saved credentials and local audio, never invoked by the default main."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--channel", type=int)
    parser.add_argument("--input-device")
    parser.add_argument("--output-device")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--port", type=int, default=8554)
    args = parser.parse_args()
    if args.list_devices:
        for direction, names in list_audio_devices().items():
            for name in names:
                print(f"{direction}: {name}")
        return
    if args.seconds is not None and (
        not math.isfinite(args.seconds) or args.seconds <= 0
    ):
        parser.error("--seconds must be finite and positive")
    configure_logging(replace_existing=True)
    saved = CameraStreamCredentials.load("data/stream_credentials.json")
    camera = Camera(
        config=load_config(),
        connection_mode="lan",
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
        channel=args.channel,
    )
    try:
        with camera.serve_rtsp(port=args.port, audio=False) as session:
            print(f"Video URL (wait for media readiness): {session.url}")
            input(
                "Open the video in VLC. Press Enter to turn on the microphone: "
            )
            handle = session.start_talk(
                input_device=args.input_device,
                output_device=args.output_device,
            )
            try:
                if args.seconds is None:
                    input("Microphone ON. Press Enter to stop conversation: ")
                else:
                    handle.wait(timeout=args.seconds)
                handle.wait(timeout=0)
            finally:
                session.stop_talk()
            print(
                "Microphone OFF. Video continues; press Ctrl+C to close preview."
            )
            session.wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

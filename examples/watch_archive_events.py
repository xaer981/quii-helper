"""Observe local archive additions, not confirmed calls or live notifications.

Run ``python -m examples.watch_archive_events`` from a configured checkout.
Reuses data/stream_credentials.json like examples.lan_rtsp. Set the camera IP
in CAMERA_DEVICE_HOST; the example uses only the file's device id/auth code.
No cloud login or key refresh is attempted, even if the file is missing.
Device automatic saving determines whether pictures/videos appear at all.
"manual" may also mean a manual monitor recording. No door commands are sent.
"""

from datetime import datetime, timedelta

from quii_helper import (
    Camera,
    CameraStreamCredentials,
    QuiiConnectionError,
    load_config,
)
from quii_helper.support.log import configure_logging


def main() -> None:
    """Poll a narrow device-local time window for three minutes."""
    configure_logging(replace_existing=True)
    try:
        config = load_config()
        saved = CameraStreamCredentials.load("data/stream_credentials.json")
        camera = Camera(
            config=config,
            connection_mode="lan",
            device_id=saved.device_id,
            auth_code=saved.auth_code,
        )
        while True:
            try:
                device_now = datetime.strptime(
                    input(
                        "Current time on the monitor (YYYY-MM-DD HH:MM:SS): "
                    ).strip(),
                    "%Y-%m-%d %H:%M:%S",
                )
                break
            except ValueError:
                print(
                    "Invalid time. Use YYYY-MM-DD HH:MM:SS "
                    "with a valid date from the monitor's clock.",
                    flush=True,
                )
        print(
            "Watching archive additions every 5 seconds for 3 minutes. "
            "Wait for 'Archive baseline ready' before testing. "
            "This is not a confirmed call detector; no door commands.",
            flush=True,
        )
        for event in camera.watch_archive_events(
            start_time=(device_now - timedelta(minutes=5)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            end_time=(device_now + timedelta(minutes=4)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            file_type="all",
            interval_seconds=5,
            duration_seconds=180,
        ):
            record = event.record
            print(
                f"{event.kind} | observed_utc={event.observed_at.isoformat()} | "
                f"type={record.file_type} | channel={record.channel_id} | "
                f"occur_type={record.occur_type} | start={record.start_time}",
                flush=True,
            )
    except KeyboardInterrupt:
        pass
    except QuiiConnectionError:
        print(
            "Archive read failed or a safety limit was reached; stopped. "
            "This does not mean that no event occurred.",
            flush=True,
        )
        raise
    print("Stopped.", flush=True)


if __name__ == "__main__":
    main()

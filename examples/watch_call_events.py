"""Poll cloud call history every five seconds for up to three minutes.

Run ``python -m examples.watch_call_events`` from a configured checkout.
Cloud account/app settings and discovery assets are required; TLS_VERIFY is
honored. Each query may create a separate alarm reader client/session.

The first successful page is a baseline. Later unseen record ids are printed
once per run, but may be delayed history, not a call happening now. Only the
first 15 rows are checked; bursts can be missed. Times remain vendor-local.
The time limit stops new polls; an in-flight query keeps its API timeouts.
No preview, downloads, notification changes, answering or door commands.
"""

from time import monotonic, sleep

from quii_helper import Camera, QuiiConnectionError, load_config
from quii_helper.support.log import configure_logging

POLL_SECONDS = 5.0
WATCH_SECONDS = 180.0


def main() -> None:
    """Observe unseen history rows until the time limit or Ctrl+C."""
    configure_logging(replace_existing=True)
    camera = Camera(config=load_config(), connection_mode="cloud")
    seen_ids: set[str] | None = None
    deadline = monotonic() + WATCH_SECONDS
    print(
        f"Watching cloud history for {WATCH_SECONDS:g} seconds; "
        f"poll interval {POLL_SECONDS:g} seconds. No door commands.",
        flush=True,
    )
    try:
        while monotonic() < deadline:
            started = monotonic()
            try:
                page = camera.get_call_events(page=0, max_id="0", page_size=15)
            except QuiiConnectionError:
                print(
                    "Cloud history query failed; keeping the baseline "
                    "and retrying on the next poll.",
                    flush=True,
                )
            else:
                if seen_ids is None:
                    seen_ids = {event.record_id for event in page.events}
                    print(
                        f"Baseline ready: {len(seen_ids)} existing records. "
                        "Watching for unseen history entries.",
                        flush=True,
                    )
                else:
                    for event in page.events:
                        if event.record_id not in seen_ids:
                            seen_ids.add(event.record_id)
                            print(
                                f"Unseen record: {event.time} | "
                                f"channel={event.channel} | "
                                f"record_id={event.record_id} | "
                                f"alarm_id={event.alarm_id}",
                                flush=True,
                            )
            delay = min(started + POLL_SECONDS, deadline) - monotonic()
            if delay > 0:
                sleep(delay)
    except KeyboardInterrupt:
        pass
    print("Stopped.", flush=True)


if __name__ == "__main__":
    main()

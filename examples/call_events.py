"""Read cloud history through a tokenless alarm login, without door control.

Run with ``python -m examples.call_events`` after configuring `.env` and assets.
The alarm login may create a separate reader client/session on the server.
"""

from quii_helper import Camera, load_config
from quii_helper.support.log import configure_logging


def main() -> None:
    """Print the first history page, omitting private resource URLs."""
    configure_logging(replace_existing=True)
    page = Camera(
        config=load_config(), connection_mode="cloud"
    ).get_call_events()
    print(
        f"Incoming calls: {len(page.events)}; "
        f"total: {page.total_count}; unread: {page.unread_count}"
    )
    for event in page.events:
        print(
            f"{event.time} | channel={event.channel} | "
            f"record_id={event.record_id} | alarm_id={event.alarm_id}"
        )


if __name__ == "__main__":
    main()

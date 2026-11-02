"""Observe LAN talk control replies and both audio sources, without sending sound.

Run ``python -m examples.diagnose_lan_talk`` explicitly with saved credentials.
This reserves preview and talk connections and can contend with the app.
No cloud login, microphone, audio playback, outgoing media or door command.
"""

import json
from dataclasses import replace

from quii_helper import CameraStreamCredentials, load_config
from quii_helper.protocols.tcp.probes.talk import diagnose_lan_talk


def main() -> None:
    """Print sanitized ten-second diagnostics; do not refresh the saved key."""
    saved = CameraStreamCredentials.load("data/stream_credentials.json")
    config = replace(
        load_config(),
        connection_mode="lan",
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    try:
        report = diagnose_lan_talk(
            config, duration_seconds=10, talk_channel=65535
        )
    except KeyboardInterrupt:
        return
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

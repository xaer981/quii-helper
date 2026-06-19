from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quii_helper.io.paths import resolve_data_path


@dataclass
class TcpLiveProbeCapture:
    client: Any
    dump_file: Path
    num_messages: int
    play_param: int = 1

    def run(self) -> dict:
        dump_file = self._prepare_dump_file()

        self.client.connect()
        setup_request = self.client.send_setup()
        setup_response = self.client.recv_setup()
        open_request = self.client.send_live_open(play_param=self.play_param)

        return {
            "setup_request": setup_request,
            "setup_response": setup_response,
            "open_request": open_request,
            "messages": self._read_messages(dump_file),
            "dump_file": str(dump_file.resolve()),
        }

    def _prepare_dump_file(self) -> Path:
        dump_file = resolve_data_path(self.dump_file)
        if dump_file.exists():
            dump_file.unlink()
        return dump_file

    def _read_messages(self, dump_file: Path) -> list[dict[str, Any]]:
        messages = []
        for _ in range(self.num_messages):
            try:
                messages.append(self.client.recv_message(dump_file=dump_file))
            except Exception as exc:
                messages.append({"error": str(exc)})
                break
        return messages

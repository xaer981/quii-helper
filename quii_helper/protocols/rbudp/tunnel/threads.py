import threading
from collections.abc import Callable
from dataclasses import dataclass

ThreadTarget = Callable[[], None]


@dataclass
class RbUdpBackgroundThreads:
    """Own background worker threads used by an RBUDP tunnel."""

    receive_loop: threading.Thread | None = None
    play_sync_loop: threading.Thread | None = None
    keepalive_loop: threading.Thread | None = None

    def start_receive_loop(self, target: ThreadTarget) -> None:
        self.receive_loop = self._start("quii-rbudp-receive", target)

    def start_play_sync_loop(self, target: ThreadTarget) -> None:
        self.play_sync_loop = self._start("quii-rbudp-play-sync", target)

    def start_keepalive_loop(self, target: ThreadTarget) -> None:
        self.keepalive_loop = self._start("quii-rbudp-keepalive", target)

    def join_all(self, *, timeout: float = 0.75) -> None:
        current = threading.current_thread()
        for thread in (
            self.play_sync_loop,
            self.keepalive_loop,
            self.receive_loop,
        ):
            if thread is None or thread is current or not thread.is_alive():
                continue
            thread.join(timeout=timeout)

    @staticmethod
    def _start(name: str, target: ThreadTarget) -> threading.Thread:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        return thread

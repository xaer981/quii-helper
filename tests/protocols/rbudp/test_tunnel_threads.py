import threading

from quii_helper.protocols.rbudp.tunnel.threads import RbUdpBackgroundThreads


class RbUdpBackgroundThreadsTests:
    def test_starts_named_daemon_threads(self) -> None:
        finished = threading.Event()
        threads = RbUdpBackgroundThreads()

        threads.start_receive_loop(finished.set)
        assert finished.wait(1.0)

        assert threads.receive_loop is not None
        assert "quii-rbudp-receive" == threads.receive_loop.name
        assert threads.receive_loop.daemon

    def test_join_all_waits_for_started_threads(self) -> None:
        stop = threading.Event()
        started = threading.Event()
        threads = RbUdpBackgroundThreads()

        def worker() -> None:
            started.set()
            stop.wait(1.0)

        threads.start_keepalive_loop(worker)
        assert started.wait(1.0)
        stop.set()
        threads.join_all(timeout=1.0)

        assert threads.keepalive_loop is not None
        assert not threads.keepalive_loop.is_alive()

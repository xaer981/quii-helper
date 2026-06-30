import queue
import time
from collections.abc import Callable
from typing import Any

from quii_helper.config import AutonomousConfig
from quii_helper.protocols.p2p.codec.json_codec import (
    parse_p2pconnect_response,
    parse_sub_device_state_response,
)
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedSubDeviceState,
)


class MqttBootstrapWaiter:
    """Waits for MQTT bootstrap responses and device state changes."""

    def __init__(
        self,
        *,
        config: AutonomousConfig,
        messages: "queue.Queue[dict[str, Any]]",
        all_messages: "queue.Queue[tuple[str, dict[str, Any]]]",
        publish_sub_device_state: Callable[[], None],
    ):
        self.config: AutonomousConfig = config
        self._messages: queue.Queue[dict[str, Any]] = messages
        self._all_messages: queue.Queue[tuple[str, dict[str, Any]]] = (
            all_messages
        )
        self._publish_sub_device_state: Callable[[], None] = (
            publish_sub_device_state
        )

    def wait_for_command(
        self, command: str, timeout: float
    ) -> tuple[str, dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            try:
                topic, payload = self._all_messages.get(timeout=remaining)
            except queue.Empty:
                continue
            header = payload.get("header") or {}
            if header.get("command") == command:
                return topic, payload
        raise TimeoutError(f"timed out waiting for MQTT command={command!r}")

    def wait_for_sub_device_state(
        self, timeout: float
    ) -> ParsedSubDeviceState:
        _topic, payload = self.wait_for_command("sub-device-state", timeout)
        return parse_sub_device_state_response(payload)

    def wait_for_device_online(
        self,
        device_id: str,
        *,
        timeout: float,
        retry_interval: float,
    ) -> ParsedSubDeviceState:
        deadline = time.time() + timeout
        next_retry_at = 0.0
        latest: ParsedSubDeviceState | None = None
        while time.time() < deadline:
            now = time.time()
            if now >= next_retry_at:
                self._publish_sub_device_state()
                next_retry_at = now + retry_interval
            remaining = min(max(0.1, deadline - now), retry_interval)
            try:
                state = self.wait_for_sub_device_state(remaining)
            except TimeoutError:
                continue
            latest = state
            if device_id in state.online:
                return state
        if latest is None:
            raise TimeoutError(
                "timed out waiting for sub-device-state response"
            )
        raise TimeoutError(
            f"device did not transition to online state; "
            f"offline={latest.offline!r} online={latest.online!r}"
        )

    def collect_messages(
        self, duration: float
    ) -> list[tuple[str, dict[str, Any]]]:
        deadline = time.time() + duration
        out: list[tuple[str, dict[str, Any]]] = []
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            try:
                out.append(self._all_messages.get(timeout=remaining))
            except queue.Empty:
                break
        return out

    def wait_p2pconnect_response(
        self, session_flag: str, timeout: float
    ) -> P2PConnectResponse:
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            try:
                payload = self._messages.get(timeout=remaining)
            except queue.Empty:
                continue
            try:
                parsed = parse_p2pconnect_response(payload)
            except Exception:
                continue
            if (
                parsed.session_flag == session_flag
                or parsed.device_id == self.config.device_id
            ):
                return parsed
        raise TimeoutError("timed out waiting for p2pconnect response")

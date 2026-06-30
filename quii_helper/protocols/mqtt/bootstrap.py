import json
import queue
import threading
from typing import Any, cast

import paho.mqtt.client as mqtt

from quii_helper.config import AutonomousConfig
from quii_helper.protocols.mqtt.publishers import MqttBootstrapPublisher
from quii_helper.protocols.mqtt.runtime import ensure_mqtt_runtime
from quii_helper.protocols.mqtt.url import parse_mqtt_url
from quii_helper.protocols.mqtt.waiters import MqttBootstrapWaiter
from quii_helper.protocols.p2p.models import (
    P2PConnectRequest,
    P2PConnectResponse,
    ParsedSubDeviceState,
)
from quii_helper.protocols.ust.credentials import decode_ust_mqtt_credentials


class MqttP2PBootstrap:
    """Coordinates MQTT bootstrap connection, publishing, and response waits."""

    def __init__(self, config: AutonomousConfig):
        self.config = config
        ensure_mqtt_runtime(self.config)
        self.parsed = parse_mqtt_url(config.ust_address)
        self._connected = threading.Event()
        self._messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._all_messages: "queue.Queue[tuple[str, dict[str, Any]]]" = (
            queue.Queue()
        )
        mqtt_runtime = cast(Any, mqtt)
        self._client: mqtt.Client = mqtt_runtime.Client(
            mqtt_runtime.CallbackAPIVersion.VERSION2,
            client_id=self.config.mqtt_client_id or "",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._publisher = MqttBootstrapPublisher(
            config=self.config,
            client=self._client,
        )
        self._waiter = MqttBootstrapWaiter(
            config=self.config,
            messages=self._messages,
            all_messages=self._all_messages,
            publish_sub_device_state=self.publish_sub_device_state,
        )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        if reason_code.is_failure:
            return
        topics = [
            f"{self.config.client_id}/ust/json",
            self.parsed.subtopic,
            self.parsed.subtopic2,
        ]
        seen: set[str] = set()
        for topic in topics:
            if topic and topic not in seen:
                client.subscribe(topic)
                seen.add(topic)
        self._connected.set()

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        self._connected.clear()

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: Any,
    ) -> None:
        try:
            decoded = json.loads(
                message.payload.decode("utf-8", errors="ignore")
            )
        except Exception:
            return
        if not isinstance(decoded, dict):
            return
        payload = cast(dict[str, Any], decoded)
        self._all_messages.put((message.topic, payload))
        self._messages.put(payload)

    def connect(self) -> None:
        self._client.tls_set(
            ca_certs=str(self.config.ca_path),
            certfile=str(self.config.cert_path),
            keyfile=str(self.config.key_path),
        )
        self._client.tls_insecure_set(True)
        if self.config.mqtt_will_topic and self.config.mqtt_will_message:
            self._client.will_set(
                self.config.mqtt_will_topic,
                self.config.mqtt_will_message,
                qos=0,
                retain=False,
            )
        mqtt_username, mqtt_password = decode_ust_mqtt_credentials(
            self.parsed, srcid=self.config.client_id
        )
        if mqtt_username or mqtt_password:
            self._client.username_pw_set(mqtt_username, mqtt_password)
        self._client.connect(self.parsed.host, self.parsed.port, keepalive=30)
        self._client.loop_start()
        if not self._connected.wait(self.config.mqtt_timeout):
            raise TimeoutError("MQTT connect timeout")

    def close(self) -> None:
        try:
            self._client.loop_stop()
        finally:
            self._client.disconnect()

    def publish_register(self) -> None:
        self._publisher.publish_register()

    def publish_unregister(self) -> None:
        self._publisher.publish_unregister()

    def publish_sub_device_state(self) -> None:
        self._publisher.publish_sub_device_state()

    def publish_p2pconnect(self, request: P2PConnectRequest) -> None:
        self._publisher.publish_p2pconnect(request)

    def publish_update_netinfo(
        self,
        *,
        public_ip: str,
        public_udp_port: int,
        local_ips: list[str],
        local_udp_port: int,
    ) -> None:
        self._publisher.publish_update_netinfo(
            public_ip=public_ip,
            public_udp_port=public_udp_port,
            local_ips=local_ips,
            local_udp_port=local_udp_port,
        )

    def wait_for_command(
        self, command: str, timeout: float
    ) -> tuple[str, dict[str, Any]]:
        return self._waiter.wait_for_command(command, timeout)

    def wait_for_sub_device_state(
        self, timeout: float
    ) -> ParsedSubDeviceState:
        return self._waiter.wait_for_sub_device_state(timeout)

    def wait_for_device_online(
        self,
        device_id: str,
        *,
        timeout: float,
        retry_interval: float,
    ) -> ParsedSubDeviceState:
        return self._waiter.wait_for_device_online(
            device_id,
            timeout=timeout,
            retry_interval=retry_interval,
        )

    def collect_messages(
        self, duration: float
    ) -> list[tuple[str, dict[str, Any]]]:
        return self._waiter.collect_messages(duration)

    def wait_p2pconnect_response(
        self, session_flag: str, timeout: float
    ) -> P2PConnectResponse:
        return self._waiter.wait_p2pconnect_response(session_flag, timeout)

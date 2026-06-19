import json
import queue
import threading
from typing import Any

import paho.mqtt.client as mqtt

from quii_helper.config import AutonomousConfig
from quii_helper.protocols.mqtt.publishers import MqttBootstrapPublishMixin
from quii_helper.protocols.mqtt.runtime import ensure_mqtt_runtime
from quii_helper.protocols.mqtt.url import parse_mqtt_url
from quii_helper.protocols.mqtt.waiters import MqttBootstrapWaitMixin
from quii_helper.protocols.ust.credentials import decode_ust_mqtt_credentials


class MqttP2PBootstrap(MqttBootstrapWaitMixin, MqttBootstrapPublishMixin):
    def __init__(self, config: AutonomousConfig):
        self.config = config
        ensure_mqtt_runtime(self.config)
        self.parsed = parse_mqtt_url(config.ust_address)
        self._connected = threading.Event()
        self._messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._all_messages: "queue.Queue[tuple[str, dict[str, Any]]]" = (
            queue.Queue()
        )
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.config.mqtt_client_id or "",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
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

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected.clear()

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(
                message.payload.decode("utf-8", errors="ignore")
            )
        except Exception:
            return
        self._all_messages.put((message.topic, payload))
        self._messages.put(payload)

    def connect(self):
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

    def close(self):
        try:
            self._client.loop_stop()
        finally:
            self._client.disconnect()

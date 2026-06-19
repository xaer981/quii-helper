from quii_helper.protocols.p2p.models import P2PConnectRequest
from quii_helper.protocols.ust.messages import (
    build_ust_register_request,
    build_ust_sub_device_state_request,
    build_ust_unregister_request,
    build_ust_update_netinfo_request,
)


class MqttBootstrapPublishMixin:
    def _app_topic(self) -> str:
        return f"app/ust/json/{self.config.client_id}"

    def publish_register(self):
        payload = build_ust_register_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(self._app_topic(), payload.encode("utf-8"), qos=0)

    def publish_unregister(self):
        payload = build_ust_unregister_request(client_id=self.config.client_id)
        self._client.publish(self._app_topic(), payload.encode("utf-8"), qos=0)

    def publish_sub_device_state(self):
        payload = build_ust_sub_device_state_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            device_ids=[self.config.device_id],
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(self._app_topic(), payload.encode("utf-8"), qos=0)

    def publish_p2pconnect(self, request: P2PConnectRequest):
        self._client.publish(
            self._app_topic(), request.to_json().encode("utf-8"), qos=0
        )

    def publish_update_netinfo(
        self,
        *,
        public_ip: str,
        public_udp_port: int,
        local_ips: list[str],
        local_udp_port: int,
    ):
        payload = build_ust_update_netinfo_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            public_ip=public_ip,
            public_udp_port=public_udp_port,
            local_ips=local_ips,
            local_udp_port=local_udp_port,
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(self._app_topic(), payload.encode("utf-8"), qos=0)

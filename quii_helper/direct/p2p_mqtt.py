import time

from quii_helper.config import AutonomousConfig
from quii_helper.protocols.mqtt.bootstrap import MqttP2PBootstrap
from quii_helper.protocols.p2p.models import (
    P2PConnectRequest,
    P2PConnectResponse,
)
from quii_helper.protocols.p2p.peer_selection import has_probe_targets


def run_mqtt_p2pconnect_attempt(
    mqtt_bootstrap: MqttP2PBootstrap,
    *,
    config: AutonomousConfig,
    request: P2PConnectRequest,
    session_flag: str,
    public_ip: str,
    public_udp_port: int,
    local_ips: list[str],
    local_udp_port: int,
    attempt_index: int,
) -> P2PConnectResponse:
    mqtt_bootstrap.connect()
    mqtt_bootstrap.publish_unregister()
    time.sleep(0.1)
    mqtt_bootstrap.publish_register()
    mqtt_bootstrap.wait_for_command("register", config.mqtt_timeout)
    wait_for_device_online(mqtt_bootstrap, config=config)
    mqtt_bootstrap.publish_p2pconnect(request)
    response = mqtt_bootstrap.wait_p2pconnect_response(
        session_flag, config.mqtt_timeout
    )
    mqtt_bootstrap.publish_update_netinfo(
        public_ip=public_ip,
        public_udp_port=public_udp_port,
        local_ips=local_ips,
        local_udp_port=local_udp_port,
    )
    if not has_probe_targets(response):
        print(
            "[P2PDiag] empty_p2pconnect_response",
            {
                "attempt": attempt_index + 1,
                "response_local_ips": response.local_ips,
                "response_local_udp_port": response.local_udp_port,
                "public_ip": response.public_ip,
                "public_udp_port": response.public_udp_port,
                "utd_public_ip": response.utd_public_ip,
                "utd_public_udp_port": response.utd_public_udp_port,
            },
        )
        raise RuntimeError("empty p2pconnect response without probe targets")
    if config.preconnect_settle_delay > 0:
        print(
            f"[Prewarm] settle delay {config.preconnect_settle_delay:.1f}s "
            "before UDP probe"
        )
        time.sleep(config.preconnect_settle_delay)
    return response


def wait_for_device_online(
    mqtt_bootstrap: MqttP2PBootstrap, *, config: AutonomousConfig
) -> None:
    try:
        state = mqtt_bootstrap.wait_for_device_online(
            config.device_id,
            timeout=config.prewarm_timeout,
            retry_interval=config.prewarm_retry_interval,
        )
        print(
            "[Prewarm] device online",
            {
                "device_ids": state.device_ids,
                "online": state.online,
                "offline": state.offline,
                "usrkey": state.usrkey,
            },
        )
    except TimeoutError as exc:
        print(f"[Prewarm] online wait timeout: {exc}")

import json
import random
import time

from quii_helper.config import AutonomousConfig


def ensure_mqtt_runtime(config: AutonomousConfig) -> None:
    if not config.mqtt_userdata:
        rng = random.Random(
            config.rng_seed
            if config.rng_seed is not None
            else int(time.time() * 1000)
        )
        config.mqtt_userdata = str(
            rng.randrange(10_000_000_000, 99_999_999_999)
        )
    if not config.mqtt_client_id:
        config.mqtt_client_id = (
            f"app_{config.client_id}_{config.mqtt_userdata}_"
        )
    if not config.mqtt_will_topic:
        config.mqtt_will_topic = f"app/ust/json/{config.client_id}"
    if not config.mqtt_will_message:
        config.mqtt_will_message = json.dumps(
            {
                "header": {
                    "flag": "tdkcloud",
                    "version": "v3.2.0",
                    "command": "unregister",
                    "userdata": config.mqtt_userdata,
                    "client": {
                        "id": config.client_id,
                    },
                }
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )


def reset_mqtt_runtime(config: AutonomousConfig) -> None:
    config.mqtt_userdata = None
    config.mqtt_client_id = None
    config.mqtt_will_topic = None
    config.mqtt_will_message = None

from quii_helper.protocols.mqtt.bootstrap import MqttP2PBootstrap


class MqttBootstrapMroTests:
    def test_bootstrap_uses_explicit_composition(self) -> None:
        assert [cls.__name__ for cls in MqttP2PBootstrap.__mro__] == [
            "MqttP2PBootstrap",
            "object",
        ]

    def test_public_publish_method_remains_available(self) -> None:
        assert callable(MqttP2PBootstrap.publish_sub_device_state)

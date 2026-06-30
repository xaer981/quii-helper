from types import SimpleNamespace

from quii_helper.protocols.rbudp.lanes.registry import RbUdpLaneRegistry


class RbUdpLaneRegistryTests:
    def _registry(self) -> RbUdpLaneRegistry:
        registry = RbUdpLaneRegistry.create(
            src_ids=[0x4000006, 0x4000007],
            bootstrap_word4=0,
            bootstrap_remote_id=1,
            bootstrap_local_ids=[0, 1],
        )
        first, second = registry.lanes
        first["word4"] = 0x3D000022
        first["word8"] = 0x1000000
        first["peer_word4"] = 0x1000000
        first["peer_word8"] = 0x3D000022
        second["word4"] = 0x3E000023
        second["word8"] = 0x2000001
        second["peer_word4"] = 0x2000001
        second["peer_word8"] = 0x3E000023
        return registry

    def test_for_packet_words_matches_peer_words(self) -> None:
        registry = self._registry()

        lane = registry.for_packet_words(word4=0x1000000, word8=0x3D000022)

        assert lane is registry.lanes[0]

    def test_for_packet_words_matches_reversed_current_words(self) -> None:
        registry = self._registry()
        registry.lanes[0]["peer_word4"] = 0
        registry.lanes[0]["peer_word8"] = 0

        lane = registry.for_packet_words(word4=0x1000000, word8=0x3D000022)

        assert lane is registry.lanes[0]

    def test_for_syn_ack_matches_bootstrap_word8(self) -> None:
        registry = self._registry()
        control = SimpleNamespace(word4=registry.lanes[1]["bootstrap_word8"])

        assert registry.for_syn_ack(control) is registry.lanes[1]

    def test_active_falls_back_to_first_lane(self) -> None:
        registry = self._registry()

        assert registry.active(0xDEADBEEF) is registry.lanes[0]

    def test_for_src_id_returns_matching_lane(self) -> None:
        registry = self._registry()

        assert registry.for_src_id(0x4000007) is registry.lanes[1]
        assert registry.for_src_id(0xDEADBEEF) is None

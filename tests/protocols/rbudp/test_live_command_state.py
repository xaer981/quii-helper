import unittest

from quii_helper.protocols.rbudp.live.command_state import (
    build_native_play_profile,
    build_quii_play_common_args,
    normalize_live_play_payload,
    select_live_command_lane_destinations,
)


class RbUdpLiveCommandStateTests(unittest.TestCase):
    def test_build_native_play_profile_matches_channel_and_stream_bits(
        self,
    ) -> None:
        profile = build_native_play_profile(
            channel=0x0201,
            stream=2,
            inner=True,
        )

        self.assertEqual(0x0201, profile["channel_id"])
        self.assertEqual(0x01, profile["packet_type"])
        self.assertEqual(0x01, profile["ext_len_low"])
        self.assertEqual(0x02, profile["ext_len_high"])
        self.assertEqual(0x01, profile["play_param"])
        self.assertEqual(0x01, profile["stream_flag"])
        self.assertEqual(1, profile["inner"])

    def test_build_native_play_profile_clamps_and_masks_values(self) -> None:
        negative = build_native_play_profile(
            channel=-1,
            stream=0,
            inner=False,
        )
        masked = build_native_play_profile(
            channel=0x12345,
            stream=300,
            inner=False,
        )

        self.assertEqual(0, negative["channel_id"])
        self.assertEqual(0, negative["stream_flag"])
        self.assertEqual(0x2345, masked["channel_id"])
        self.assertEqual(43, masked["stream_flag"])

    def test_normalize_live_play_payload_accepts_supported_values(
        self,
    ) -> None:
        self.assertEqual("path", normalize_live_play_payload("PATH"))
        self.assertEqual("oem", normalize_live_play_payload("oem"))

    def test_normalize_live_play_payload_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            normalize_live_play_payload("token")

    def test_build_quii_play_common_args_matches_native_crypto_defaults(
        self,
    ) -> None:
        profile = build_native_play_profile(
            channel=1,
            stream=2,
            inner=True,
        )

        common = build_quii_play_common_args(
            src_id=0x4000006,
            dest_id=0x12340000,
            seq=7,
            profile=profile,
            data_encode_key=b"key",
        )

        self.assertEqual(0x4000006, common["src_id"])
        self.assertEqual(0x12340000, common["dest_id"])
        self.assertEqual(7, common["seq"])
        self.assertEqual(0x01, common["packet_type"])
        self.assertEqual(0x01, common["ext_len_low"])
        self.assertEqual(0x00, common["ext_len_high"])
        self.assertEqual(0x01, common["play_param"])
        self.assertEqual(0x01, common["stream_flag"])
        self.assertIs(True, common["inner"])
        self.assertEqual(2, common["crypto_mode"])
        self.assertEqual(b"key", common["key"])
        self.assertIs(True, common["encrypt"])

    def test_select_live_command_lane_destinations_prefers_active_src(
        self,
    ) -> None:
        lanes = [({"src_id": 1}, 100), ({"src_id": 2}, 200)]

        selected = select_live_command_lane_destinations(
            lanes,
            active_src_id=2,
        )

        self.assertEqual([({"src_id": 2}, 200)], selected)

    def test_select_live_command_lane_destinations_falls_back_to_first(
        self,
    ) -> None:
        lanes = [({"src_id": 1}, 100), ({"src_id": 2}, 200)]

        selected = select_live_command_lane_destinations(
            lanes,
            active_src_id=3,
        )

        self.assertEqual([({"src_id": 1}, 100)], selected)


if __name__ == "__main__":
    unittest.main()

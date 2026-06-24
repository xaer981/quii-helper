import unittest

from quii_helper.preview.summaries.media_summary_state import (
    decoded_media_frames,
    frame_nal_sample,
    initial_nal_collection_state,
    media_decrypt_stats,
    nal_collection_payload,
    record_frame_nal_summary,
)


class PreviewMediaSummaryStateTests(unittest.TestCase):
    def test_media_decrypt_stats_counts_candidates_and_applied_packets(
        self,
    ) -> None:
        stats = media_decrypt_stats(
            [
                {"media_decrypt_candidate_len": 10},
                {
                    "media_decrypt_candidate_len": 0,
                    "media_decrypt_applied": True,
                    "media_decrypt_len": 7,
                },
                {
                    "media_decrypt_candidate_len": 3,
                    "media_decrypt_applied": True,
                    "media_decrypt_len": 5,
                },
            ]
        )

        self.assertEqual(
            {
                "media_decrypt_candidate_packets": 2,
                "media_decrypt_candidate_bytes": 13,
                "media_decrypt_packets": 2,
                "media_decrypt_bytes": 12,
            },
            stats,
        )

    def test_frame_nal_sample_keeps_existing_summary_shape(self) -> None:
        sample = frame_nal_sample(
            {"frame_tag": 0xE1, "frame_len": 42, "cframe_fragments": 3},
            {
                "counts": {"sps": 1},
                "has_sps": True,
                "has_pps": False,
                "has_idr": True,
                "nal_units": [1, 2, 3, 4],
            },
        )

        self.assertEqual("0xe1", sample["frame_tag"])
        self.assertEqual(42, sample["frame_len"])
        self.assertEqual(3, sample["cframe_fragments"])
        self.assertEqual({"sps": 1}, sample["nal"]["counts"])
        self.assertEqual([1, 2, 3], sample["nal"]["nal_units"])

    def test_decoded_media_frames_preserves_single_and_list_shapes(
        self,
    ) -> None:
        frame = {"frame_tag": 0xE1}

        self.assertEqual([frame], decoded_media_frames({"media_frame": frame}))
        self.assertEqual(
            [frame],
            decoded_media_frames({"media_frames": [frame, "bad"]}),
        )
        self.assertEqual([], decoded_media_frames({"media_frame": "bad"}))

    def test_nal_collection_state_accumulates_counts_and_flags(self) -> None:
        state = initial_nal_collection_state()

        record_frame_nal_summary(
            state,
            {"frame_tag": 0xE1, "frame_len": 12},
            {
                "counts": {"sps": 1, "idr_slice": 1},
                "has_sps": True,
                "has_pps": False,
                "has_idr": True,
                "has_vcl": True,
                "nal_units": [1, 2, 3, 4],
            },
        )
        record_frame_nal_summary(
            state,
            {"frame_tag": 0xE0, "frame_len": 8},
            {
                "counts": {"sps": 2, "pps": 1},
                "has_sps": False,
                "has_pps": True,
                "has_idr": False,
                "has_vcl": False,
                "nal_units": [],
            },
        )

        payload = nal_collection_payload(state)

        self.assertEqual(1, payload["keyframes"])
        self.assertTrue(payload["has_sps"])
        self.assertTrue(payload["has_pps"])
        self.assertTrue(payload["has_idr"])
        self.assertTrue(payload["has_vcl"])
        self.assertEqual(
            {"sps": 3, "idr_slice": 1, "pps": 1},
            payload["counts"],
        )
        self.assertEqual(2, len(payload["nal_samples"]))
        self.assertTrue(payload["decodable_h264_context"])

    def test_nal_collection_state_respects_sample_limit(self) -> None:
        state = initial_nal_collection_state()

        for _ in range(3):
            record_frame_nal_summary(
                state,
                {"frame_tag": 0xE0},
                {"counts": {}, "nal_units": []},
                sample_limit=2,
            )

        self.assertEqual(2, len(nal_collection_payload(state)["nal_samples"]))


if __name__ == "__main__":
    unittest.main()

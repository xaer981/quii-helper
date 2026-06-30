from quii_helper.preview.summaries.media_summary_state import (
    decoded_media_frames,
    frame_nal_sample,
    initial_nal_collection_state,
    media_decrypt_stats,
    nal_collection_payload,
    record_frame_nal_summary,
)


class PreviewMediaSummaryStateTests:
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

        assert {
            "media_decrypt_candidate_packets": 2,
            "media_decrypt_candidate_bytes": 13,
            "media_decrypt_packets": 2,
            "media_decrypt_bytes": 12,
        } == (stats)

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

        assert "0xe1" == sample["frame_tag"]
        assert 42 == sample["frame_len"]
        assert 3 == sample["cframe_fragments"]
        assert {"sps": 1} == sample["nal"]["counts"]
        assert [1, 2, 3] == sample["nal"]["nal_units"]

    def test_decoded_media_frames_preserves_single_and_list_shapes(
        self,
    ) -> None:
        frame = {"frame_tag": 0xE1}

        assert [frame] == decoded_media_frames({"media_frame": frame})
        assert [frame] == (
            decoded_media_frames({"media_frames": [frame, "bad"]})
        )
        assert [] == decoded_media_frames({"media_frame": "bad"})

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

        assert 1 == payload["keyframes"]
        assert payload["has_sps"]
        assert payload["has_pps"]
        assert payload["has_idr"]
        assert payload["has_vcl"]
        assert {"sps": 3, "idr_slice": 1, "pps": 1} == (payload["counts"])
        assert 2 == len(payload["nal_samples"])
        assert payload["decodable_h264_context"]

    def test_nal_collection_state_respects_sample_limit(self) -> None:
        state = initial_nal_collection_state()

        for _ in range(3):
            record_frame_nal_summary(
                state,
                {"frame_tag": 0xE0},
                {"counts": {}, "nal_units": []},
                sample_limit=2,
            )

        assert 2 == len(nal_collection_payload(state)["nal_samples"])

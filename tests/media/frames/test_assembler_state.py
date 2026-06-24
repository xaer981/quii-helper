import unittest

from quii_helper.media.frames.assembler_state import (
    access_unit_from_frame,
    assemble_access_units,
    build_media_summary,
    frame_info_from_parsed_frame,
    is_key_frame_info,
    is_video_frame_info,
    media_frame_length_stats,
)


def _parsed_frame(**overrides):
    frame = {
        "payload_offset": 20,
        "frame_tag": 0xE1,
        "frame_type": 1,
        "frame_len": 1000,
        "frame_stamp": 123,
        "codec": 1,
        "fps": 25.0,
        "width": 960,
        "height": 576,
        "nal_offset": 4,
        "bitstream": b"skipdata",
    }
    frame.update(overrides)
    return frame


class MediaAssemblerStateTests(unittest.TestCase):
    def test_frame_info_from_parsed_frame_keeps_summary_shape(self) -> None:
        frame = _parsed_frame(cframe_fragments=2)

        self.assertEqual(
            {
                "payload_offset": 20,
                "frame_tag": "0xe1",
                "frame_type": 1,
                "frame_len": 1000,
                "frame_stamp": 123,
                "codec": 1,
                "fps": 25.0,
                "width": 960,
                "height": 576,
                "nal_offset": 4,
                "cframe_fragments": 2,
            },
            frame_info_from_parsed_frame(frame),
        )

    def test_access_unit_from_frame_filters_non_video_or_missing_nal(
        self,
    ) -> None:
        self.assertEqual(b"data", access_unit_from_frame(_parsed_frame()))
        self.assertEqual(
            b"",
            access_unit_from_frame(_parsed_frame(frame_tag=0xE3)),
        )
        self.assertEqual(
            b"",
            access_unit_from_frame(_parsed_frame(nal_offset=-1)),
        )

    def test_assemble_access_units_skips_empty_units(self) -> None:
        frames = [
            _parsed_frame(bitstream=b"1234data", nal_offset=4),
            _parsed_frame(bitstream=b"1234", nal_offset=4),
        ]

        self.assertEqual([b"data"], assemble_access_units(frames))

    def test_media_summary_matches_existing_frame_counters(self) -> None:
        frames = [
            {
                "frame_tag": "0xe1",
                "frame_type": 1,
                "frame_len": 1000,
            },
            {
                "frame_tag": "0xe0",
                "frame_type": 0,
                "frame_len": 1400,
            },
            {
                "frame_tag": "0xe3",
                "frame_type": 3,
                "frame_len": 10,
            },
        ]

        summary = build_media_summary(
            frames,
            assembled_units=2,
            cframe_stats={"completed": 2},
        )

        self.assertEqual(2, summary["video_frames"])
        self.assertEqual(1, summary["keyframes"])
        self.assertEqual(1, summary["e3_frames"])
        self.assertEqual(2, summary["assembled_units"])
        self.assertEqual({"completed": 2}, summary["cframe_pack"])
        self.assertEqual(1200, summary["avg_video_frame_len"])
        self.assertEqual(1400, summary["max_video_frame_len"])
        self.assertFalse(summary["suspect_black_stream"])

    def test_media_summary_marks_small_video_stream_as_suspect(self) -> None:
        summary = build_media_summary(
            [{"frame_tag": "0xe0", "frame_type": 0, "frame_len": 100}],
            assembled_units=1,
            cframe_stats={},
        )

        self.assertTrue(summary["suspect_black_stream"])

    def test_frame_type_and_keyframe_helpers(self) -> None:
        self.assertTrue(is_video_frame_info({"frame_type": "1"}))
        self.assertFalse(is_video_frame_info({"frame_type": "3"}))
        self.assertTrue(is_key_frame_info({"frame_tag": "0xe1"}))
        self.assertFalse(is_key_frame_info({"frame_tag": "0xe0"}))

    def test_media_frame_length_stats_handles_empty_video_list(self) -> None:
        self.assertEqual((0, 0), media_frame_length_stats([]))


if __name__ == "__main__":
    unittest.main()

import hashlib
from pathlib import Path

from quii_helper.preview.fragments.embedded_h264_state import (
    embedded_h264_paths,
    embedded_h264_result_payload,
    empty_embedded_h264_result,
    should_write_persistent_embedded,
)


class PreviewEmbeddedH264StateTests:
    def test_embedded_h264_paths_preserve_filename_shape(self) -> None:
        paths = embedded_h264_paths("sample")

        assert "sample_embedded.h264" == paths["stream_path"].name
        assert "sample_embedded.mp4" == paths["mp4_path"].name
        assert "sample_embedded.jpg" == paths["snapshot_path"].name
        assert "sample_embedded_best.h264" == (paths["persistent_path"].name)

    def test_should_write_persistent_embedded_skips_false_positive_sps(
        self,
    ) -> None:
        assert not should_write_persistent_embedded(
            {"false_positive_sps_only": True}
        )
        assert should_write_persistent_embedded({})

    def test_empty_embedded_h264_result_preserves_existing_shape(self) -> None:
        paths = {
            "stream_path": Path("stream.h264"),
            "mp4_path": Path("video.mp4"),
            "snapshot_path": Path("image.jpg"),
            "persistent_path": Path("best.h264"),
        }

        result = empty_embedded_h264_result(
            paths=paths,
            persistent_before=b"previous",
        )

        assert 0 == result["candidate_count"]
        assert "none" == result["merge_strategy"]
        assert "none" == result["persistent_merge_strategy"]
        assert [] == result["candidate_lens"]
        assert 8 == result["persistent_previous_len"]
        assert 0 == result["selected_len"]
        assert not result["written"]
        assert not result["mp4"]
        assert not result["snapshot"]
        assert str(paths["stream_path"].resolve()) == (result["stream_path"])

    def test_embedded_h264_result_payload_preserves_shape(self) -> None:
        paths = {
            "stream_path": Path("stream.h264"),
            "mp4_path": Path("video.mp4"),
            "snapshot_path": Path("image.jpg"),
            "persistent_path": Path("best.h264"),
        }

        result = embedded_h264_result_payload(
            unique=[b"a", b"bb"],
            selected=b"bb",
            merge_strategy="longest",
            persistent_strategy="right_extends_left",
            persistent_before=b"a",
            nal_analysis={"has_sps": True},
            persistent_written=True,
            mp4_ok=True,
            mp4_error="",
            snapshot_ok=False,
            snapshot_error="snapshot failed",
            ffmpeg_skipped_reason="",
            paths=paths,
        )

        assert 2 == result["candidate_count"]
        assert "longest" == result["merge_strategy"]
        assert "right_extends_left" == (result["persistent_merge_strategy"])
        assert [1, 2] == result["candidate_lens"]
        assert 1 == result["persistent_previous_len"]
        assert 2 == result["selected_len"]
        assert hashlib.sha1(b"bb").hexdigest() == (result["selected_sha1"])
        assert {"has_sps": True} == result["nal_analysis"]
        assert result["written"]
        assert result["persistent_written"]
        assert result["mp4"]
        assert "" == result["mp4_error"]
        assert not result["snapshot"]
        assert "snapshot failed" == result["snapshot_error"]
        assert "" == result["ffmpeg_skipped_reason"]

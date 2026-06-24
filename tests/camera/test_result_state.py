import unittest
from pathlib import Path

from quii_helper.camera.outputs.result_state import (
    capture_done_message_for_artifact,
    capture_media_artifact,
    optional_artifact_path,
)


class CameraResultStateTests(unittest.TestCase):
    def test_capture_media_artifact_prefers_media_result(self) -> None:
        summary = {
            "media_result": {"source": "media"},
            "embedded_fallback": {"source": "fallback"},
        }

        self.assertEqual({"source": "media"}, capture_media_artifact(summary))

    def test_capture_media_artifact_falls_back_to_embedded_result(
        self,
    ) -> None:
        self.assertEqual(
            {"source": "fallback"},
            capture_media_artifact(
                {"embedded_fallback": {"source": "fallback"}}
            ),
        )

    def test_capture_media_artifact_returns_empty_dict_without_artifact(
        self,
    ) -> None:
        self.assertEqual({}, capture_media_artifact({}))

    def test_optional_artifact_path_preserves_existing_coercion(self) -> None:
        self.assertIsNone(optional_artifact_path(""))
        self.assertIsNone(optional_artifact_path(None))
        self.assertEqual(Path("out.mp4"), optional_artifact_path("out.mp4"))

    def test_capture_done_message_for_artifact_preserves_branch_order(
        self,
    ) -> None:
        self.assertEqual(
            "Done. Video saved: video.mp4",
            capture_done_message_for_artifact(
                {
                    "mp4": True,
                    "mp4_path": "video.mp4",
                    "snapshot": True,
                    "snapshot_path": "snapshot.jpg",
                }
            ),
        )
        self.assertEqual(
            "Done. Snapshot saved: snapshot.jpg",
            capture_done_message_for_artifact(
                {
                    "snapshot": True,
                    "snapshot_path": "snapshot.jpg",
                }
            ),
        )
        self.assertEqual(
            "Done. Media data was collected, but no final file was written",
            capture_done_message_for_artifact({"written": True}),
        )
        self.assertEqual(
            "Done. No media file was produced",
            capture_done_message_for_artifact({}),
        )


if __name__ == "__main__":
    unittest.main()

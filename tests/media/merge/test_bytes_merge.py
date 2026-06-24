import unittest

from quii_helper.media.h264.merge.annexb_merge import merge_annexb_candidates
from quii_helper.media.merge.binary import merge_binary_candidates
from quii_helper.media.merge.bytes import (
    suffix_prefix_overlap,
    unique_blobs_by_sha1,
)


class MediaBytesMergeTests(unittest.TestCase):
    def test_unique_blobs_by_sha1_keeps_longest_first_and_dedupes(
        self,
    ) -> None:
        blobs = [b"ab", b"abcdef", b"ab", b"abcd"]

        self.assertEqual(
            [b"abcdef", b"abcd", b"ab"], unique_blobs_by_sha1(blobs)
        )

    def test_suffix_prefix_overlap_respects_minimum(self) -> None:
        self.assertEqual(3, suffix_prefix_overlap(b"abcdef", b"defgh"))
        self.assertEqual(
            0,
            suffix_prefix_overlap(b"abcdef", b"defgh", min_overlap=4),
        )

    def test_merge_binary_candidates_preserves_overlap_strategy(self) -> None:
        left = b"A" * 4 + b"B" * 16
        right = b"B" * 16 + b"C" * 4

        unique, stream, strategy = merge_binary_candidates([left, right])

        self.assertEqual([left, right], unique)
        self.assertEqual(b"A" * 4 + b"B" * 16 + b"C" * 4, stream)
        self.assertEqual("suffix_prefix_overlap:16", strategy)

    def test_merge_binary_candidates_uses_minimum_overlap(self) -> None:
        _, stream, strategy = merge_binary_candidates(
            [b"A" * 20 + b"X", b"X" + b"B" * 20]
        )

        self.assertEqual(b"A" * 20 + b"X", stream)
        self.assertEqual("longest", strategy)

    def test_merge_annexb_candidates_keeps_any_overlap_behavior(self) -> None:
        unique, stream, strategy = merge_annexb_candidates(
            [b"A" * 20 + b"X", b"X" + b"B" * 20]
        )

        self.assertEqual([b"A" * 20 + b"X", b"X" + b"B" * 20], unique)
        self.assertEqual(b"A" * 20 + b"X" + b"B" * 20, stream)
        self.assertEqual("merged", strategy)


if __name__ == "__main__":
    unittest.main()

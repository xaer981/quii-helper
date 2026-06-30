from quii_helper.media.h264.merge.annexb_merge import merge_annexb_candidates
from quii_helper.media.merge.binary import merge_binary_candidates
from quii_helper.media.merge.bytes import (
    suffix_prefix_overlap,
    unique_blobs_by_sha1,
)


class MediaBytesMergeTests:
    def test_unique_blobs_by_sha1_keeps_longest_first_and_dedupes(
        self,
    ) -> None:
        blobs = [b"ab", b"abcdef", b"ab", b"abcd"]

        assert [b"abcdef", b"abcd", b"ab"] == unique_blobs_by_sha1(blobs)

    def test_suffix_prefix_overlap_respects_minimum(self) -> None:
        assert 3 == suffix_prefix_overlap(b"abcdef", b"defgh")
        assert 0 == (suffix_prefix_overlap(b"abcdef", b"defgh", min_overlap=4))

    def test_merge_binary_candidates_preserves_overlap_strategy(self) -> None:
        left = b"A" * 4 + b"B" * 16
        right = b"B" * 16 + b"C" * 4

        unique, stream, strategy = merge_binary_candidates([left, right])

        assert [left, right] == unique
        assert b"A" * 4 + b"B" * 16 + b"C" * 4 == stream
        assert "suffix_prefix_overlap:16" == strategy

    def test_merge_binary_candidates_uses_minimum_overlap(self) -> None:
        _, stream, strategy = merge_binary_candidates(
            [b"A" * 20 + b"X", b"X" + b"B" * 20]
        )

        assert b"A" * 20 + b"X" == stream
        assert "longest" == strategy

    def test_merge_annexb_candidates_keeps_any_overlap_behavior(self) -> None:
        unique, stream, strategy = merge_annexb_candidates(
            [b"A" * 20 + b"X", b"X" + b"B" * 20]
        )

        assert [b"A" * 20 + b"X", b"X" + b"B" * 20] == unique
        assert b"A" * 20 + b"X" + b"B" * 20 == stream
        assert "merged" == strategy

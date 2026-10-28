from quii_helper.media.frames.selection import SnapshotWarmup


def test_zero_warmup_preserves_first_decodable_frame():
    state = SnapshotWarmup()
    assert not state.observe(1, decodable=False, now=20)
    assert state.observe(1, decodable=True, now=30)
    assert SnapshotWarmup(deadline=1).observe(1, decodable=True, now=2)


def test_warmup_needs_fresh_video_not_idle_time_or_audio():
    state = SnapshotWarmup(1)
    assert not state.observe(1, decodable=True, now=30)
    assert not state.observe(2, decodable=True, now=30.5)
    assert not state.observe(2, decodable=True, now=35)
    assert state.observe(3, decodable=True, now=35.1)


def test_bursty_frames_do_not_substitute_for_elapsed_warmup():
    state = SnapshotWarmup(1)
    assert not state.observe(1, decodable=True, now=30)
    assert not state.observe(100, decodable=True, now=30)
    assert state.observe(101, decodable=True, now=31)


def test_late_frame_after_capture_deadline_cannot_finish_warmup():
    state = SnapshotWarmup(1, deadline=2)
    assert not state.observe(1, decodable=True, now=0.5)
    assert not state.observe(2, decodable=True, now=2.1)
    assert not state.ready

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from quii_helper import AutonomousConfig, Camera
from quii_helper.camera.outputs.paths import output_base_from_path
from quii_helper.io.paths import (
    resolve_data_dir,
    resolve_data_path,
    timestamped_output_base,
)
from quii_helper.media.h264.io.writer_state import h264_output_paths
from quii_helper.preview.outputs.writer.output_writer import (
    PreviewOutputWriter,
)
from quii_helper.preview.outputs.writer.state import (
    resolve_preview_output_base,
)


def test_absolute_paths_are_not_remapped_into_default_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = tmp_path / "application"
    application.mkdir()
    monkeypatch.chdir(application)
    external = tmp_path / "captures"
    assert resolve_data_dir(external) == external
    assert resolve_data_path(external / "clip.mp4") == external / "clip.mp4"
    assert not (application / "data").exists()


def test_relative_default_outputs_follow_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_data_path("clip.mp4") == tmp_path / "data" / "clip.mp4"
    assert resolve_data_path("data/clip.mp4") == tmp_path / "data" / "clip.mp4"


def test_capture_and_media_writer_preserve_explicit_output_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "external" / "clip.mp4"
    base = resolve_preview_output_base(
        output_base_from_path(target), tmp_path / "other"
    )
    assert base == target.with_suffix("")
    assert h264_output_paths(base)[1] == target
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "name", ["clip.1.mp4", "frame.front.jpg", "clip.jpg.mp4"]
)
def test_dotted_capture_names_survive_the_complete_output_path(tmp_path, name):
    target = tmp_path / name
    base = resolve_preview_output_base(output_base_from_path(target), tmp_path)
    paths = h264_output_paths(base)
    assert paths[1 if target.suffix == ".mp4" else 2] == target


def test_numbered_captures_do_not_collide_with_each_other(tmp_path):
    targets = [
        tmp_path / name for name in ("clip.mp4", "clip.1.mp4", "clip.2.mp4")
    ]
    actual = [
        h264_output_paths(
            resolve_preview_output_base(output_base_from_path(path), tmp_path)
        )[1]
        for path in targets
    ]
    assert actual == targets


def test_camera_binds_paths_at_construction_without_creating_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    camera = Camera(
        AutonomousConfig(), assets_dir="native", data_dir="captures"
    )
    monkeypatch.chdir(tmp_path.parent)
    assert camera.config.assets_dir == tmp_path / "native"
    assert camera.config.ca_path == tmp_path / "native" / "ca.pem"
    assert camera.data_dir == tmp_path / "captures"
    assert not camera.config.assets_dir.exists()
    assert not camera.data_dir.exists()


def test_explicit_tls_paths_override_assets_directory(tmp_path: Path) -> None:
    certificate = tmp_path / "certificates" / "ca.pem"
    camera = Camera(
        AutonomousConfig(), assets_dir=tmp_path / "native", ca_path=certificate
    )
    assert camera.config.ca_path == certificate
    assert camera.config.cert_path == tmp_path / "native" / "client.pem"


@pytest.mark.parametrize("timestamp_format", ["same", "same.001"])
def test_concurrent_automatic_output_names_are_reserved_atomically(
    tmp_path: Path,
    timestamp_format: str,
):
    with ThreadPoolExecutor(max_workers=16) as pool:
        paths = list(
            pool.map(
                lambda _: timestamped_output_base(
                    tmp_path, timestamp_format=timestamp_format
                ),
                range(64),
            )
        )
    assert len(set(paths)) == 64
    assert all(path.with_name(path.name + ".h264").is_file() for path in paths)
    assert tmp_path / timestamp_format in paths


@pytest.mark.parametrize("fails", [False, True])
def test_unused_automatic_reservation_is_removed(tmp_path, monkeypatch, fails):
    writer = PreviewOutputWriter(data_dir=tmp_path)
    collector = SimpleNamespace(
        container_probe_candidates=[],
        cpacket_candidates=[],
        embedded_h264_candidates=[],
    )
    if fails:

        def fail(*args, **kwargs):
            raise RuntimeError("render failed")

        monkeypatch.setattr(
            "quii_helper.preview.outputs.writer.output_writer.write_h264_stream",
            fail,
        )
        with pytest.raises(RuntimeError, match="render failed"):
            writer.write_capture_outputs(
                decoded_messages=[{}], fragment_partial_collector=collector
            )
    else:
        writer.write_capture_outputs(
            decoded_messages=[], fragment_partial_collector=collector
        )
    assert list(tmp_path.iterdir()) == []

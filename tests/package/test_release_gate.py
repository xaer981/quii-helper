import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / ".github/scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_snapshot_does_not_read_secrets_or_generated_files(
    tmp_path, monkeypatch
):
    gate = load_script("release_gate")
    names = [
        "README.md",
        ".env.example",
        ".env",
        ".env.private",
        "assets/x.so",
        "data/video.mp4",
        "venv/config",
        ".venv/config",
    ]
    monkeypatch.setattr(gate, "git", lambda *_: "\0".join(names))
    (tmp_path / "README.md").write_text("public")
    (tmp_path / ".env.example").write_text("TOKEN=")
    # Excluded paths deliberately do not exist: reading them would fail.
    assert set(gate.public_sources(tmp_path)) == {"README.md", ".env.example"}


def test_offline_suite_blocks_real_network_before_sending():
    import socket

    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="camera/cloud"):
            sock.connect(("192.0.2.1", 80))
    with socket.socket(type=socket.SOCK_DGRAM) as sock:
        with pytest.raises(AssertionError, match="camera/cloud"):
            sock.sendto(b"synthetic", ("192.0.2.1", 80))


def test_gate_rejects_dirty_candidate_before_creating_outputs(
    tmp_path, monkeypatch
):
    gate = load_script("release_gate")
    monkeypatch.setattr(gate, "git", lambda *_: " M README.md")
    with pytest.raises(ValueError, match="committed and clean"):
        gate.release_gate(tmp_path, allow_dirty=False, soak_seconds=120)
    assert not (tmp_path / "data").exists()


def test_failed_subprocess_is_recorded_and_stops_gate(tmp_path, monkeypatch):
    gate = load_script("release_gate")
    monkeypatch.setattr(gate, "git", lambda *_: "candidate")
    monkeypatch.setattr(gate, "public_sources", lambda _: {})
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        Mock(side_effect=subprocess.CalledProcessError(1, "synthetic")),
    )
    with pytest.raises(subprocess.CalledProcessError):
        gate.release_gate(tmp_path, allow_dirty=True, soak_seconds=3)
    (report_path,) = (tmp_path / "data/release-gate").glob("*/report.json")
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert report["manual_camera_check"].startswith("pending")
    assert report["checks"] == [
        {"name": "dependencies", "status": "failed", "log": "dependencies.log"}
    ]


@pytest.mark.parametrize(
    "dirty,seconds,status",
    [
        (True, 120, "development_pass_not_release_candidate"),
        (False, 3, "development_pass_not_release_candidate"),
        (False, 119, "development_pass_not_release_candidate"),
        (False, 120, "automated_pass"),
    ],
)
def test_gate_distinguishes_development_checks_from_release_candidate(
    tmp_path, monkeypatch, dirty, seconds, status
):
    gate = load_script("release_gate")
    monkeypatch.setattr(
        gate,
        "git",
        lambda _, *args: (
            (" M README.md" if dirty else "")
            if args[0] == "status"
            else "candidate"
        ),
    )
    monkeypatch.setattr(gate, "public_sources", lambda _: {})

    def fake_check(name, command, *, source, output, report):
        report["checks"].append({"name": name, "status": "passed"})
        if name == "build":
            (output / "dist").mkdir()
            (output / "dist/candidate.whl").write_bytes(b"synthetic")

    monkeypatch.setattr(gate, "run_check", fake_check)
    path = gate.release_gate(tmp_path, allow_dirty=dirty, soak_seconds=seconds)
    report = json.loads(path.read_text())
    assert report["status"] == status
    assert report["artifact_sha256"]["candidate.whl"]
    assert report["checks"][-1]["name"] == "installed-tests-and-soak"


def test_gate_fails_when_source_changes_during_checks(tmp_path, monkeypatch):
    gate = load_script("release_gate")
    monkeypatch.setattr(gate, "git", lambda *_: "candidate")
    monkeypatch.setattr(
        gate, "public_sources", Mock(side_effect=[{}, {"new": "hash"}])
    )

    def fake_check(name, command, *, source, output, report):
        if name == "build":
            (output / "dist").mkdir()

    monkeypatch.setattr(gate, "run_check", fake_check)
    with pytest.raises(ValueError, match="sources changed"):
        gate.release_gate(tmp_path, allow_dirty=True, soak_seconds=3)
    (path,) = (tmp_path / "data/release-gate").glob("*/report.json")
    assert json.loads(path.read_text())["status"] == "failed"


def test_installed_checks_use_both_archives_and_isolated_imports(
    tmp_path, monkeypatch
):
    check = load_script("check_install")
    for suffix in (".whl", ".tar.gz"):
        (tmp_path / f"synthetic{suffix}").touch()
    monkeypatch.setattr(check.venv.EnvBuilder, "create", lambda *_: None)
    run = Mock()
    monkeypatch.setattr(check.subprocess, "run", run)
    check.check_install(tmp_path, soak_seconds=3)
    commands = [call.args[0] for call in run.call_args_list]
    assert len([cmd for cmd in commands if "--smoke" in cmd]) == 2
    tests = [cmd for cmd in commands if "-c" in cmd]
    assert len(tests) == 2
    assert all(
        "-I" in cmd and "--import-mode=importlib" in " ".join(cmd)
        for cmd in tests
    )
    assert sum("--seconds" in cmd for cmd in commands) == 2
    assert sum("--audio" in cmd for cmd in commands) == 1
    assert commands.index(
        next(cmd for cmd in commands if "--smoke" in cmd)
    ) < commands.index(tests[0])


def test_installed_smoke_accepts_noncanonical_working_directory(
    tmp_path, monkeypatch
):
    import quii_helper

    check = load_script("check_install")
    root = tmp_path.resolve()
    monkeypatch.chdir(root)
    (root / "alias").mkdir()
    alias = root / "alias" / ".."
    assert alias != root and alias.resolve() == root
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: alias))
    # The suite also exercises this check against an installed package.
    monkeypatch.setattr(
        check.sys,
        "prefix",
        str(Path(quii_helper.__file__).resolve().parents[1]),
    )

    check.smoke()

    assert not (root / "data").exists()
    assert not (root / "assets").exists()


@pytest.mark.parametrize("audio", [False, True])
def test_synthetic_soak_runs_without_camera_or_assets(audio):
    soak = load_script("check_rtsp_soak")
    report = soak.run_soak(3, audio=audio)
    assert report["received_frames"] > 0
    assert report["slow_disconnects"] == 1
    assert report["worker_cleanup"] == "passed"
    assert report["audio_enabled"] is audio
    assert (report["received_audio_packets"] > 0) is audio


def test_ci_release_gate_requires_all_jobs_and_reuses_checked_archives():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    publish = (ROOT / ".github/workflows/publish.yml").read_text()
    assert "needs: [secret-scan, test, build, install, rtsp-soak]" in workflow
    assert 'value["result"] != "success"' in workflow
    assert "--seconds 120" in workflow
    assert "--seconds 120 --audio" in workflow
    assert "uses: ./.github/workflows/ci.yml" in publish
    assert "needs: checks" in publish

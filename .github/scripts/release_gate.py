"""Check a frozen public source snapshot; never publish or contact a camera."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MIN_SOAK_SECONDS = 120
PRIVATE_ROOTS = {"assets", "data", "venv", ".venv", ".git"}


def git(root: Path, *arguments: str) -> str:
    return (
        subprocess.check_output(["git", *arguments], cwd=root)
        .decode("utf-8")
        .strip()
    )


def public_sources(root: Path) -> dict[str, str]:
    """Hash only public inputs, never open extracted assets or real env files."""
    names = git(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).split("\0")
    manifest = {}
    for name in sorted(set(filter(None, names))):
        relative = Path(name)
        if relative.parts[0] in PRIVATE_ROOTS or any(
            part.startswith(".env") and part != ".env.example"
            for part in relative.parts
        ):
            continue
        if relative.suffix.lower() in {".so", ".pem", ".key"}:
            raise ValueError(f"private asset listed as public source: {name}")
        source = root / relative
        if any(
            parent.is_symlink()
            for parent in [source, *source.parents]
            if parent != root and parent.is_relative_to(root)
        ) or not source.resolve().is_relative_to(root):
            raise ValueError(f"unsafe source path: {name}")
        if source.is_file():
            manifest[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    return manifest


def run_check(
    name: str, command: list[str], *, source: Path, output: Path, report: dict
) -> None:
    """Record failures too; a failed subprocess can never produce a green gate."""
    log = output / f"{name}.log"
    check = {"name": name, "status": "failed", "log": log.name}
    report["checks"].append(check)
    print(f"CHECK {name}", flush=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(
            command,
            cwd=source,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
        )
    check["status"] = "passed"


def release_gate(
    root: Path, *, allow_dirty: bool, soak_seconds: float
) -> Path:
    root = root.resolve()
    dirty = bool(git(root, "status", "--porcelain"))
    if dirty and not allow_dirty:
        raise ValueError("release candidate must be committed and clean")
    if soak_seconds < 3:
        raise ValueError("soak duration must be at least 3 seconds")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "data" / "release-gate" / stamp
    output.mkdir(parents=True)
    report = {
        "status": "failed",
        "commit": git(root, "rev-parse", "HEAD"),
        "dirty": dirty,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "soak_seconds": soak_seconds,
        "manual_camera_check": "pending; owner must test this exact candidate",
        "checks": [],
    }
    try:
        manifest = public_sources(root)
        source = output / "source"
        source.mkdir()
        for name in manifest:
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
            if (
                hashlib.sha256(target.read_bytes()).hexdigest()
                != manifest[name]
            ):
                raise ValueError("source changed while creating the snapshot")
        (output / "source-sha256.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        dist = output / "dist"
        python = sys.executable
        commands = [
            ("dependencies", [python, "-m", "pip", "check"]),
            ("lint", [python, "-m", "ruff", "check", "--no-cache", "."]),
            ("format", [python, "-m", "black", "--check", "--no-cache", "."]),
            (
                "types",
                [
                    python,
                    "-m",
                    "mypy",
                    "quii_helper",
                    "--strict",
                    "--no-incremental",
                    "--cache-dir",
                    str(output / "mypy"),
                ],
            ),
            (
                "tests",
                [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            ),
            (
                "secrets",
                [
                    "go",
                    "run",
                    "github.com/zricethezav/gitleaks/v8@v8.30.1",
                    "dir",
                    "--config",
                    ".gitleaks.toml",
                    "--redact",
                    "--no-banner",
                    ".",
                ],
            ),
            (
                "workflows",
                [
                    "go",
                    "run",
                    "github.com/rhysd/actionlint/cmd/actionlint@v1.7.12",
                    "-shellcheck=",
                    ".github/workflows/ci.yml",
                    ".github/workflows/publish.yml",
                ],
            ),
            ("build", [python, "-m", "build", "--outdir", str(dist)]),
        ]
        for name, command in commands:
            run_check(
                name, command, source=source, output=output, report=report
            )
        artifacts = sorted(dist.iterdir())
        report["artifact_sha256"] = {
            item.name: hashlib.sha256(item.read_bytes()).hexdigest()
            for item in artifacts
        }
        for name, command in (
            (
                "metadata",
                [
                    python,
                    "-m",
                    "twine",
                    "check",
                    "--strict",
                    *map(str, artifacts),
                ],
            ),
            (
                "archives",
                [python, ".github/scripts/check_distribution.py", str(dist)],
            ),
            (
                "installed-tests-and-soak",
                [
                    python,
                    ".github/scripts/check_install.py",
                    str(dist),
                    "--soak-seconds",
                    str(soak_seconds),
                ],
            ),
        ):
            run_check(
                name, command, source=source, output=output, report=report
            )
        if manifest != public_sources(root):
            raise ValueError(
                "public sources changed while the gate was running"
            )
        if report["commit"] != git(root, "rev-parse", "HEAD"):
            raise ValueError(
                "candidate commit changed while the gate was running"
            )
        report["status"] = (
            "automated_pass"
            if not dirty and soak_seconds >= MIN_SOAK_SECONDS
            else "development_pass_not_release_candidate"
        )
    finally:
        path = output / "report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"REPORT {path}", flush=True)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--soak-seconds", type=float, default=MIN_SOAK_SECONDS)
    arguments = parser.parse_args()
    release_gate(
        Path(__file__).resolve().parents[2],
        allow_dirty=arguments.allow_dirty,
        soak_seconds=arguments.soak_seconds,
    )

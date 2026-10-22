"""Install both archives outside the checkout without camera or cloud I/O."""

import argparse
import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from unittest.mock import patch


def smoke() -> None:
    """Verify installed imports, explicit configuration and host logging."""
    from loguru import logger

    Path(".env").write_text("CAMERA_APP_ID=invalid\n", encoding="utf-8")
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)))
    with (
        patch(
            "dotenv.dotenv_values",
            side_effect=AssertionError("implicit env read"),
        ),
        patch(
            "dotenv.load_dotenv",
            side_effect=AssertionError("implicit env load"),
        ),
        patch("socket.socket.connect", side_effect=AssertionError("network")),
        patch("socket.socket.sendto", side_effect=AssertionError("network")),
        patch("threading.Thread.start", side_effect=AssertionError("thread")),
        patch(
            "pathlib.Path.mkdir", side_effect=AssertionError("directory write")
        ),
    ):
        import quii_helper
        from quii_helper import AutonomousConfig, Camera

        package = Path(quii_helper.__file__).resolve().parent
        assert package.is_relative_to(Path(sys.prefix).resolve())
        assert (package / "py.typed").is_file()
        camera = Camera(AutonomousConfig(app_id=17))
        assert camera.config.app_id == 17
        assert camera.data_dir == Path.cwd() / "data"
        assert camera.config.assets_dir == Path.cwd() / "assets"
    logger.info("host sink survived")
    logger.remove(sink)
    assert len(messages) == 1 and "host sink survived" in messages[0]
    assert not Path("data").exists() and not Path("assets").exists()
    print("Installed library OK:", importlib.metadata.version("quii-helper"))


def check_install(directory: Path, *, soak_seconds: float = 0) -> None:
    """Install wheel and sdist into distinct disposable virtual environments."""
    for suffix in ("*.whl", "*.tar.gz"):
        artifacts = list(directory.resolve().glob(suffix))
        if len(artifacts) != 1:
            raise ValueError("expected one artifact of each distribution type")
        with tempfile.TemporaryDirectory(prefix="quii-install-") as temporary:
            root = Path(temporary)
            venv.EnvBuilder(with_pip=True).create(root / "env")
            executable = (
                root
                / "env"
                / (
                    "Scripts/python.exe"
                    if sys.platform == "win32"
                    else "bin/python"
                )
            )
            subprocess.run(
                [str(executable), "-m", "pip", "install", str(artifacts[0])],
                cwd=root,
                check=True,
            )
            subprocess.run(
                [str(executable), "-m", "pip", "check"], cwd=root, check=True
            )
            subprocess.run(
                [
                    str(executable),
                    "-I",
                    str(Path(__file__).resolve()),
                    "--smoke",
                ],
                cwd=root,
                check=True,
            )
            # Test the installed artifact, not an editable checkout.
            subprocess.run(
                [
                    str(executable),
                    "-m",
                    "pip",
                    "install",
                    f"{artifacts[0]}[dev]",
                ],
                cwd=root,
                check=True,
            )
            source = Path(__file__).resolve().parents[2]
            consumer = root / "consumer"
            consumer.mkdir()
            shutil.copytree(source / "examples", consumer / "examples")
            subprocess.run(
                [
                    str(executable),
                    "-I",
                    "-B",
                    "-c",
                    "import sys; from pathlib import Path; "
                    "sys.path.insert(0, str(Path.cwd())); "
                    "import quii_helper, pytest; "
                    "assert Path(quii_helper.__file__).resolve().is_relative_to("
                    "Path(sys.prefix).resolve()); "
                    "raise SystemExit(pytest.main(['-q', '--import-mode=importlib', "
                    "'-p', 'no:cacheprovider', sys.argv[1]]))",
                    str(source / "tests"),
                ],
                cwd=consumer,
                check=True,
            )
            if suffix == "*.whl" and soak_seconds:
                subprocess.run(
                    [
                        str(executable),
                        "-I",
                        "-B",
                        str(source / ".github/scripts/check_rtsp_soak.py"),
                        "--seconds",
                        str(soak_seconds),
                    ],
                    cwd=consumer,
                    check=True,
                )
            subprocess.run(
                [str(executable), "-m", "pip", "check"], cwd=root, check=True
            )


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke"]:
        smoke()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("directory", type=Path)
        parser.add_argument("--soak-seconds", type=float, default=0)
        arguments = parser.parse_args()
        check_install(arguments.directory, soak_seconds=arguments.soak_seconds)

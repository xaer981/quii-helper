"""Check public documentation without private settings or network calls."""

import ast
import inspect
import re
import unicodedata
from io import StringIO
from pathlib import Path
from unittest.mock import patch, sentinel
from urllib.parse import unquote, urlsplit

import black
import pytest
from dotenv import dotenv_values

from quii_helper import (
    AutonomousConfig,
    Camera,
    CameraStreamCredentials,
    load_config,
)
from quii_helper.cloud.config.runtime import validate_runtime_config
from quii_helper.config.validation import (
    REQUIRED_CAMERA_APP_FIELDS,
    validate_camera_app_config,
)

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = sorted(
    [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md")]
    + list((ROOT / ".github").rglob("*.md"))
)
PYTHON_BLOCK = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
ENV_BLOCK = re.compile(r"```dotenv\s*\n(.*?)```", re.DOTALL)
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)\)")
METHOD_ROW = re.compile(r"^\| `([a-z_]+\([^`]*\))` \|", re.MULTILINE)


def heading_ids(text: str) -> set[str]:
    """Match GitHub-style ids, including duplicate headings and Unicode marks."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    result: set[str] = set()
    seen: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", text, re.MULTILINE):
        heading = re.sub(r"<[^>]+>", "", heading).lower()
        slug = "".join(
            char
            for char in heading
            if char in "_ -" or unicodedata.category(char)[0] in "LNM"
        ).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def repository_target(source: Path, url: str) -> tuple[Path, str] | None:
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if not parsed.scheme:
        target = (source.parent / path).resolve() if path else source
    elif parsed.netloc == "github.com":
        root_url = "/xaer981/quii-helper"
        if path.rstrip("/") == root_url:
            target = ROOT / "README.md"
        else:
            prefixes = (f"{root_url}/blob/main/", f"{root_url}/tree/main/")
            prefix = next((p for p in prefixes if path.startswith(p)), None)
            if prefix is None:
                return None
            target = ROOT / path[len(prefix) :]
    else:
        return None
    return target, unquote(parsed.fragment)


def test_heading_ids_handle_code_duplicates_and_emoji() -> None:
    text = "# Quick Start \U0001f680\n## `Camera()`\n## `Camera()`\n```\n# Hidden\n```"
    assert heading_ids(text) == {"quick-start-", "camera", "camera-1"}


@pytest.mark.parametrize(
    "document", DOCUMENTS, ids=lambda p: str(p.relative_to(ROOT))
)
def test_repository_documentation_links(document: Path) -> None:
    for url in LINK.findall(document.read_text(encoding="utf-8")):
        resolved = repository_target(document, url)
        if resolved is None:
            continue
        target, fragment = resolved
        assert target.exists(), f"{document}: missing link target {url}"
        if fragment and target.suffix == ".md":
            assert fragment in heading_ids(
                target.read_text(encoding="utf-8")
            ), f"{document}: missing anchor {url}"


def test_issue_contact_links_target_existing_sections() -> None:
    source = ROOT / ".github/ISSUE_TEMPLATE/config.yml"
    for url in re.findall(
        r"^\s+url:\s+(\S+)", source.read_text(), re.MULTILINE
    ):
        resolved = repository_target(source, url)
        assert resolved is not None
        target, fragment = resolved
        assert target.exists()
        if fragment:
            assert fragment in heading_ids(target.read_text(encoding="utf-8"))


def test_readme_links_work_outside_a_checkout() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert all(urlsplit(url).scheme == "https" for url in LINK.findall(text))


def test_readme_quick_start_works_without_repository_examples() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    quick_start = text.split("## Quick Start", 1)[1].split(
        "## RTSP Streaming", 1
    )[0]
    assert "python -m pip install quii-helper" in quick_start
    assert "fetch_stream_credentials()" in quick_start
    assert "CameraStreamCredentials.load(" in quick_start
    assert "python -m examples." not in quick_start
    assert "git clone" not in quick_start


@pytest.mark.parametrize("document", ["README.md", "docs/setup.md"])
def test_first_run_documents_all_required_cloud_settings(
    document: str, tmp_path: Path
) -> None:
    text = (ROOT / document).read_text(encoding="utf-8")
    block = next(
        block for block in ENV_BLOCK.findall(text) if "CLOUD_ACCOUNT=" in block
    )
    values = dotenv_values(stream=StringIO(block), interpolate=False)
    required = set(REQUIRED_CAMERA_APP_FIELDS.values()) | {
        "CLOUD_ACCOUNT",
        "CLOUD_PASSWORD",
        "DEVICE_ID",
    }
    assert set(values) == required
    assert all(values.values())
    assert text.index(block) < text.index(
        "cloud_camera.fetch_stream_credentials()"
    )
    numeric = {"CAMERA_APP_ID", "CAMERA_CLIENT_TYPE", "IP_REGION_ID"}
    config = load_config(
        project_root=tmp_path,
        env={
            name: "1" if name in numeric else "synthetic-value"
            for name in values
        },
    )
    validate_runtime_config(config)
    validate_camera_app_config(config)


@pytest.mark.parametrize("document", ["README.md", "docs/setup.md"])
def test_later_run_documents_only_local_settings(
    document: str, tmp_path: Path
) -> None:
    text = (ROOT / document).read_text(encoding="utf-8")
    block = next(
        block
        for block in ENV_BLOCK.findall(text)
        if "CAMERA_DEVICE_HOST=" in block
    )
    values = dotenv_values(stream=StringIO(block), interpolate=False)
    assert set(values) == {
        "CAMERA_CONNECTION_MODE",
        "CAMERA_DEVICE_HOST",
        "CAMERA_STREAM_PORT",
        "CAMERA_CHANNEL",
        "CAMERA_STREAM",
    }
    config = load_config(
        project_root=tmp_path,
        env={
            name: value for name, value in values.items() if value is not None
        },
    )
    assert values["CAMERA_STREAM"] == "low"
    assert config.stream == 2
    saved = CameraStreamCredentials(
        "synthetic-device", "K" * 32, "synthetic-auth"
    )
    camera = Camera(
        config=config,
        connection_mode="lan",
        device_id=saved.device_id,
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    assert camera.config.connection_mode == "lan"
    assert camera.config.device_host == "192.0.2.10"
    assert not camera.config.cloud_account
    assert not camera.config.cloud_password
    assert not camera.config.auth_url


def test_all_runnable_examples_are_listed_in_api_guide() -> None:
    text = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    for example in (ROOT / "examples").glob("*.py"):
        if example.stem != "__init__":
            assert f"python -m examples.{example.stem}" in text


@pytest.mark.parametrize(
    "document", ["README.md", "docs/api.md", "docs/setup.md"]
)
def test_documented_saved_key_rtsp_stays_lan_with_cloud_settings(
    document: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    saved = CameraStreamCredentials(
        "synthetic-device", "K" * 32, "synthetic-auth"
    )
    config = AutonomousConfig(
        connection_mode="cloud", device_host="192.0.2.10"
    )
    blocks = PYTHON_BLOCK.findall(
        (ROOT / document).read_text(encoding="utf-8")
    )
    source = next(
        block
        for block in blocks
        if "CameraStreamCredentials.load(" in block
        and "camera.serve_rtsp(" in block
    )
    with (
        patch("quii_helper.load_config", return_value=config),
        patch("quii_helper.CameraStreamCredentials.load", return_value=saved),
        patch.object(Camera, "serve_rtsp", autospec=True) as serve,
        patch.object(
            Camera,
            "fetch_stream_credentials",
            side_effect=AssertionError("bootstrap forbidden"),
        ),
        patch(
            "quii_helper.camera.connection.session.fetch_runtime_credentials",
            side_effect=AssertionError("cloud forbidden"),
        ),
        patch("builtins.print"),
    ):
        exec(compile(source, document, "exec"), {})
    camera = serve.call_args.args[0]
    assert camera.config.connection_mode == "lan"
    assert camera.config.stream_key == saved.stream_key
    assert camera.config.auth_code == saved.auth_code
    assert camera.config.device_id == saved.device_id
    assert config.connection_mode == "cloud"


def test_api_method_tables_match_camera_signatures() -> None:
    text = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    tables = re.findall(
        r"^\| Method \|.*?(?=\n\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    documented: set[str] = set()
    for signature in METHOD_ROW.findall("\n".join(tables)):
        call = ast.parse(signature, mode="eval").body
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        name = call.func.id
        method = getattr(Camera, name, None)
        assert callable(method), f"documented Camera.{name} does not exist"
        documented.add(name)
        if (
            call.args
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value is Ellipsis
        ):
            continue
        inspect.signature(method).bind(
            None,
            *(object() for _ in call.args),
            **{keyword.arg: object() for keyword in call.keywords},
        )
    public = {
        name
        for name, _ in inspect.getmembers(Camera, inspect.isfunction)
        if not name.startswith("_")
    }
    assert documented == public


def test_setup_documents_every_environment_template_key() -> None:
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    setup = (ROOT / "docs/setup.md").read_text(encoding="utf-8")
    keys = re.findall(r"^([A-Z_]+)=", template, re.MULTILINE)
    assert keys
    assert all(f"`{key}`" in setup for key in keys)


def test_api_documents_every_constructor_parameter() -> None:
    text = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    for name in inspect.signature(Camera).parameters:
        assert (
            f"`{name}`" in text
        ), f"missing Camera constructor option: {name}"


@pytest.mark.parametrize(
    "document", DOCUMENTS, ids=lambda p: str(p.relative_to(ROOT))
)
def test_python_examples_use_mocked_public_api(
    document: Path, tmp_path: Path
) -> None:
    blocks = PYTHON_BLOCK.findall(document.read_text(encoding="utf-8"))
    with (
        patch("quii_helper.Camera", autospec=True) as camera_cls,
        patch("quii_helper.CameraStreamCredentials", autospec=True),
        patch("quii_helper.load_config", return_value=sentinel.config),
        patch(
            "dotenv.dotenv_values",
            side_effect=AssertionError("private env read"),
        ),
        patch(
            "dotenv.load_dotenv",
            side_effect=AssertionError("private env load"),
        ),
        patch("loguru.logger.enable"),
        patch("builtins.print"),
    ):
        for block in blocks:
            assert (
                black.format_str(
                    block,
                    mode=black.Mode(
                        line_length=79,
                        target_versions={black.TargetVersion.PY310},
                    ),
                )
                == block
            ), f"unformatted Python example in {document}"
            code = compile(ast.parse(block), str(document), "exec")
            exec(
                code,
                {
                    "camera": camera_cls.return_value,
                    "__file__": str(tmp_path / "app.py"),
                },
            )

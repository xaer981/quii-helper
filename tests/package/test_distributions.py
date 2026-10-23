import io
import runpy
import tarfile
import zipfile
from pathlib import Path

import pytest

CHECKS = runpy.run_path(
    str(
        Path(__file__).resolve().parents[2]
        / ".github/scripts/check_distribution.py"
    )
)
VERSION = "0.1.0"
TAG = "v0.1.0"


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        (TAG, VERSION),
        ("v0.1.1", "0.1.1"),
        ("v0.2.0", "0.2.0"),
        ("v0.1.0-rc.6", "0.1.0rc6"),
        ("v0.1.0rc6", "0.1.0rc6"),
    ],
)
def test_release_tag_matches_normalized_package_version(
    tag: str, version: str
) -> None:
    CHECKS["check_tag"](tag, version)


@pytest.mark.parametrize("tag", ["main", "0.1.0", "v0.1.0-rc.6", "v0.1.1"])
def test_release_tag_mismatch_is_rejected(tag: str) -> None:
    with pytest.raises(ValueError):
        CHECKS["check_tag"](tag, VERSION)


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        "config/.env.prod",
        "assets/client.txt",
        "data/private.jsonl",
        "client.pem",
        "lib.so",
        "../outside",
        "/absolute",
        "config\\.env",
    ],
)
def test_private_and_unsafe_members_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        CHECKS["check_members"]({name})


def make_distributions(
    directory: Path,
    *,
    private: bool = False,
    different: bool = False,
    license_expression: str = "MIT",
) -> None:
    metadata = f"Name: quii-helper\nVersion: {VERSION}\nLicense-Expression: {license_expression}\nLicense-File: LICENSE\n\n".encode()
    package = {"quii_helper/__init__.py": b"", "quii_helper/py.typed": b""}
    dist_info = f"quii_helper-{VERSION}.dist-info/"
    with zipfile.ZipFile(directory / "package.whl", "w") as archive:
        for name, content in {
            **package,
            dist_info + "METADATA": metadata,
            dist_info + "licenses/LICENSE": b"MIT",
        }.items():
            archive.writestr(name, content)
    source = {
        **package,
        "PKG-INFO": metadata,
        "LICENSE": b"MIT",
        "README.md": b"readme",
        ".env.example": b"",
        "pyproject.toml": b"",
        "docs/README.md": b"",
        "examples/snapshot.py": b"",
        "tests/package/test_public_api.py": b"",
        ".github/scripts/check_distribution.py": b"",
    }
    if private:
        source["assets/client.txt"] = b"synthetic sentinel"
    if different:
        source["quii_helper/__init__.py"] = b"different"
    with tarfile.open(directory / "package.tar.gz", "w:gz") as archive:
        for name, content in source.items():
            member = tarfile.TarInfo(f"quii_helper-{VERSION}/{name}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def test_complete_distributions_have_matching_sources_and_license(
    tmp_path: Path,
) -> None:
    make_distributions(tmp_path)
    assert CHECKS["check_distributions"](tmp_path, TAG) == VERSION


@pytest.mark.parametrize(
    "kwargs",
    [
        {"private": True},
        {"different": True},
        {"license_expression": "BSD-3-Clause"},
    ],
)
def test_distribution_regressions_are_rejected(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    make_distributions(tmp_path, **kwargs)
    with pytest.raises(ValueError):
        CHECKS["check_distributions"](tmp_path, TAG)


def test_empty_artifact_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one wheel and one sdist"):
        CHECKS["check_distributions"](tmp_path)

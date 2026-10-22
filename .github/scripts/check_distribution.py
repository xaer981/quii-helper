"""Reject incomplete/private release archives and mismatched release tags."""

import os
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from packaging.version import Version


def check_tag(tag: str, version: str) -> None:
    """Require a v-prefixed tag whose PEP 440 version matches the package."""
    if not tag.startswith("v") or Version(tag[1:]) != Version(version):
        raise ValueError("release tag does not match distribution version")


def check_members(names: set[str]) -> None:
    """Keep credentials, extracted binaries and generated data out of archives."""
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("unsafe archive member")
        if (
            set(path.parts)
            & {"assets", "data", "venv", ".venv", "__pycache__"}
            or any(
                part.startswith(".env") and part != ".env.example"
                for part in path.parts
            )
            or path.suffix.lower()
            in {".pem", ".key", ".so", ".pyc", ".mp4", ".jpg", ".h264", ".log"}
        ):
            raise ValueError("private or generated file in distribution")


def check_distributions(directory: Path, tag: str = "") -> str:
    """Check both archives, SPDX metadata, type marker and source parity."""
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("expected exactly one wheel and one sdist")
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel = {name: archive.read(name) for name in archive.namelist()}
    with tarfile.open(sources[0]) as archive:
        source = {}
        for member in archive.getmembers():
            if not member.isfile():
                if not member.isdir():
                    raise ValueError("links or special files in sdist")
                continue
            stream = archive.extractfile(member)
            if stream is not None:
                source[member.name] = stream.read()
    check_members(set(wheel) | set(source))
    metadata_names = [
        name for name in wheel if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        raise ValueError("expected one wheel metadata record")
    metadata_path = PurePosixPath(metadata_names[0])
    metadata = BytesParser().parsebytes(wheel[str(metadata_path)])
    version = metadata["Version"]
    if (
        metadata["Name"] != "quii-helper"
        or metadata["License-Expression"] != "MIT"
        or metadata.get_all("License-File") != ["LICENSE"]
        or str(metadata_path.parent / "licenses/LICENSE") not in wheel
    ):
        raise ValueError("missing package identity or SPDX license metadata")
    root = "quii_helper-" + version + "/"
    required = {
        "PKG-INFO",
        "LICENSE",
        "README.md",
        ".env.example",
        "pyproject.toml",
        "docs/README.md",
        "examples/snapshot.py",
        "tests/package/test_public_api.py",
        ".github/scripts/check_distribution.py",
    }
    if not all(root + name in source for name in required):
        raise ValueError("sdist is missing required sources or documentation")
    source_metadata = BytesParser().parsebytes(source[root + "PKG-INFO"])
    if source_metadata["Version"] != version:
        raise ValueError("wheel and sdist versions differ")
    package = {
        name: data
        for name, data in wheel.items()
        if name.startswith("quii_helper/")
    }
    source_package = {
        name[len(root) :]: data
        for name, data in source.items()
        if name.startswith(root + "quii_helper/")
    }
    if "quii_helper/py.typed" not in package or package != source_package:
        raise ValueError("wheel and sdist package contents differ")
    if tag:
        check_tag(tag, version)
    return version


if __name__ == "__main__":
    release_tag = (
        os.environ.get("GITHUB_REF_NAME", "")
        if os.environ.get("GITHUB_REF_TYPE") == "tag"
        else ""
    )
    print(
        "Checked distributions:",
        check_distributions(Path(sys.argv[1]), release_tag),
    )

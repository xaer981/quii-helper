"""Public API contracts, discovered from exports rather than a manual list."""

import inspect
import re
from dataclasses import dataclass, fields, is_dataclass
from types import GenericAlias
from typing import (
    Annotated,
    ForwardRef,
    Literal,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

import pytest

import quii_helper


def _public_objects(exports):
    pending = list(exports)
    result = {}
    seen = set()
    while pending:
        name, obj = pending.pop()
        if id(obj) in seen or not (
            inspect.isclass(obj) or inspect.isfunction(obj)
        ):
            continue
        seen.add(id(obj))
        result[name] = obj
        if inspect.isclass(obj):
            members = {}
            for base in reversed(obj.__mro__):
                members.update(vars(base))
            for member_name, member in members.items():
                if member_name.startswith("_"):
                    continue
                if isinstance(member, (classmethod, staticmethod)):
                    member = member.__func__
                elif isinstance(member, property):
                    member = member.fget
                if inspect.isfunction(member):
                    pending.append((f"{name}.{member_name}", member))
            if name == "Camera":
                pending.append(("Camera.__init__", obj.__init__))
        else:
            try:
                returns = [get_type_hints(obj).get("return")]
            except Exception as exc:
                raise AssertionError(f"{name}: invalid annotations") from exc
            while returns:
                value = returns.pop()
                if get_origin(value) is Literal:
                    continue
                arguments = get_args(value)
                returns.extend(
                    arguments[:1]
                    if get_origin(value) is Annotated
                    else arguments
                )
                if inspect.isclass(value) and value.__module__.startswith(
                    "quii_helper."
                ):
                    pending.append((value.__qualname__, value))
    return result


def _missing_docstrings(objects):
    return sorted(
        name
        for name, obj in objects.items()
        if not (getattr(obj, "__doc__", None) or "").strip()
    )


def _documented_names(obj, section):
    doc = inspect.cleandoc(getattr(obj, "__doc__", None) or "")
    match = re.search(rf"(?m)^{re.escape(section)}:\n((?:[ \t].*|\n)*)", doc)
    if match is None:
        return set()
    return set(re.findall(r"(?m)^[ \t]+(\w+):[ \t]*\S.*$", match.group(1)))


def _missing_field_docs(objects):
    missing = []
    for name, obj in objects.items():
        if inspect.isclass(obj) and is_dataclass(obj):
            expected = {field.name for field in fields(obj)}
        elif is_typeddict(obj):
            expected = set(get_type_hints(obj))
        else:
            continue
        documented = _documented_names(obj, "Attributes")
        missing.extend(
            f"{name}.{field}"
            for field in expected - documented
            if not field.startswith("_")
        )
    return sorted(missing)


def _exports():
    return [(name, getattr(quii_helper, name)) for name in quii_helper.__all__]


def _unresolved_types(annotation):
    if isinstance(annotation, (str, ForwardRef)):
        return [annotation]
    if get_origin(annotation) is Literal:
        return []
    arguments = get_args(annotation)
    if get_origin(annotation) is Annotated:
        arguments = arguments[:1]
    return [item for arg in arguments for item in _unresolved_types(arg)]


class PublicDocstringTests:
    def test_high_level_api_has_docstrings(self) -> None:
        assert _missing_docstrings(_public_objects(_exports())) == []

    def test_public_model_fields_are_documented(self) -> None:
        assert _missing_field_docs(_public_objects(_exports())) == []

    def test_camera_parameters_are_documented(self) -> None:
        missing = []
        for name, obj in _public_objects(_exports()).items():
            if not name.startswith("Camera.") or not inspect.isfunction(obj):
                continue
            documented = _documented_names(obj, "Args")
            missing.extend(
                f"{name}.{parameter}"
                for parameter in inspect.signature(obj).parameters
                if parameter not in {"self", "cls"} | documented
            )
        assert sorted(missing) == []

    def test_public_annotations_resolve(self) -> None:
        for name, obj in _public_objects(_exports()).items():
            try:
                hints = get_type_hints(obj)
            except Exception as exc:
                raise AssertionError(f"{name}: invalid annotations") from exc
            for field, annotation in hints.items():
                assert not _unresolved_types(annotation), f"{name}.{field}"


@pytest.mark.parametrize("kind", ["method", "property", "class", "static"])
def test_new_public_members_cannot_escape_doc_check(kind):
    class AddedApi:
        """An exported class added after the original API list."""

    def added(self):
        pass

    member = {
        "method": added,
        "property": property(added),
        "class": classmethod(added),
        "static": staticmethod(added),
    }[kind]
    setattr(AddedApi, "added", member)
    assert _missing_docstrings(_public_objects([("AddedApi", AddedApi)])) == [
        "AddedApi.added"
    ]


def test_private_helpers_are_not_public_contracts():
    class AddedApi:
        """Only public members require documentation."""

        def _helper(self):
            pass

    assert _missing_docstrings(_public_objects([("AddedApi", AddedApi)])) == []


def test_undocumented_override_cannot_inherit_a_docstring():
    class Base:
        """A documented base class."""

        def method(self):
            """An inherited description is not the override's contract."""

    class AddedApi(Base):
        """An exported subclass."""

        def method(self):
            pass

    assert _missing_docstrings(_public_objects([("AddedApi", AddedApi)])) == [
        "AddedApi.method"
    ]


def test_inherited_public_members_are_checked():
    class Base:
        def method(self):
            pass

    class AddedApi(Base):
        """An exported subclass that inherits its public method."""

    assert _missing_docstrings(_public_objects([("AddedApi", AddedApi)])) == [
        "AddedApi.method"
    ]


def test_new_model_fields_cannot_escape_doc_check():
    @dataclass
    class AddedModel:
        """A model with one missing field description.

        Attributes:
            known: A documented integer.
            added:
        """

        known: int
        added: int

    assert _missing_field_docs({"AddedModel": AddedModel}) == [
        "AddedModel.added"
    ]


def test_returned_sessions_are_discovered_automatically():
    objects = _public_objects(_exports())
    assert "CameraRtspStream" in objects
    assert "CameraRtspStream.start_talk" in objects
    assert "CameraRtspStreamStats" in objects


def test_return_metadata_is_not_a_public_session():
    class Metadata:
        pass

    Metadata.__module__ = "quii_helper.testing"

    def added() -> None:
        """Return a library session with opaque annotation metadata."""

    added.__annotations__["return"] = Annotated[
        quii_helper.CameraAudioStream, Metadata
    ]
    objects = _public_objects([("AddedApi", added)])
    assert "CameraAudioStream" in objects
    assert Metadata not in objects.values()


def test_nested_forward_references_cannot_remain_strings():
    assert _unresolved_types(
        dict[str, GenericAlias(list, "MissingResult")]
    ) == ["MissingResult"]
    assert _unresolved_types(ForwardRef("MissingResult"))
    assert not _unresolved_types(Annotated[Literal["lan", "cloud"], "mode"])


def test_alarm_schedule_resolves_to_the_actual_model():
    assert (
        get_type_hints(quii_helper.CameraDeviceAlarmDetailChannelInfo)[
            "schedule"
        ]
        == list[quii_helper.CameraDevicePirScheduleDayInfo]
    )


def test_broken_forward_reference_is_reported():
    def added() -> None:
        """A method with an unresolvable result annotation."""

    added.__annotations__["return"] = "MissingPublicResult"
    with pytest.raises(AssertionError, match="AddedApi: invalid annotations"):
        _public_objects([("AddedApi", added)])


def test_model_sections_do_not_count_other_sections_as_field_docs():
    @dataclass
    class AddedModel:
        """A model whose field is mentioned only in an example.

        Attributes:
            other: Not the actual field.

        Examples:
            added: This is not an attribute description.
        """

        added: int

    assert _missing_field_docs({"AddedModel": AddedModel}) == [
        "AddedModel.added"
    ]

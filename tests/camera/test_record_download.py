from unittest.mock import patch

import pytest

from quii_helper import AutonomousConfig, Camera, CameraDeviceRecordFileInfo
from quii_helper.camera import api as camera_api
from quii_helper.support.errors import (
    CameraCaptureError,
    ConfigurationError,
    QuiiConnectionError,
)


@pytest.fixture
def camera() -> Camera:
    return Camera(
        config=AutonomousConfig(
            connection_mode="lan",
            device_host="192.0.2.10",
            stream_port=34567,
            stream_key="K" * 32,
            auth_code="synthetic-auth",
        )
    )


@pytest.mark.parametrize(
    "options, timeout, max_bytes",
    [
        ({}, 30.0, 16 * 1024 * 1024),
        ({"timeout": 2.5, "max_bytes": 4096}, 2.5, 4096),
    ],
)
def test_download_record_delegates(
    camera, options, timeout, max_bytes
) -> None:
    entry = CameraDeviceRecordFileInfo(
        file_type="picture",
        file_name="archive-file",
        picture_index="0007",
        url="https://ignored.invalid/archive.jpg",
    )
    jpeg = b"\xff\xd8mock-jpeg\xff\xd9"
    with patch.object(
        camera_api, "download_record_bytes", autospec=True, return_value=jpeg
    ) as download:
        assert camera.download_record(entry, **options) is jpeg

    download.assert_called_once_with(
        camera.config,
        entry,
        timeout=timeout,
        max_bytes=max_bytes,
        temporary_directory=camera.data_dir,
        protocol="default",
    )
    assert download.call_args.args[0] is camera.config
    assert download.call_args.args[1] is entry


def test_download_record_forwards_protocol(camera) -> None:
    entry = CameraDeviceRecordFileInfo(
        file_type="picture", file_name="archive-file", picture_index="0007"
    )
    jpeg = b"\xff\xd8mock-jpeg\xff\xd9"
    with patch.object(
        camera_api, "download_record_bytes", autospec=True, return_value=jpeg
    ) as download:
        assert camera.download_record(entry, protocol="pipelined") is jpeg

    assert download.call_args.kwargs["protocol"] == "pipelined"


@pytest.mark.parametrize(
    "error_type", [ConfigurationError, QuiiConnectionError, CameraCaptureError]
)
def test_download_record_preserves_protocol_errors(camera, error_type) -> None:
    entry = CameraDeviceRecordFileInfo()
    error = error_type("protocol failure")
    with patch.object(
        camera_api, "download_record_bytes", autospec=True, side_effect=error
    ) as download:
        with pytest.raises(error_type) as caught:
            camera.download_record(entry)

    assert caught.value is error
    download.assert_called_once_with(
        camera.config,
        entry,
        timeout=30.0,
        max_bytes=16 * 1024 * 1024,
        temporary_directory=camera.data_dir,
        protocol="default",
    )

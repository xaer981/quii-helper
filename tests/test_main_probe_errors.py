from dataclasses import dataclass

from quii_helper.device.cgi import DeviceCgiResponse
from quii_helper.main import STATUS_WARN, _classify_result


@dataclass(frozen=True)
class FakeDeviceResult:
    error: int
    raw: DeviceCgiResponse | None = None


class MainProbeErrorDescriptionTests:
    def test_device_error_includes_native_description(self) -> None:
        value = FakeDeviceResult(
            error=-4,
            raw=DeviceCgiResponse(
                command="get.fake",
                error=-4,
                content={},
                raw_xml="",
            ),
        )

        status, note = _classify_result(value)

        assert status == STATUS_WARN
        assert "device_error=-4" in note
        assert "CGI_ERROR_PASSWORD" in note

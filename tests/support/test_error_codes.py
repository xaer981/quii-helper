from quii_helper.support.error_codes import (
    describe_error_code,
    lookup_error_codes,
)


class ErrorCodeLookupTests:
    def test_known_sdk_error_is_described(self) -> None:
        description = describe_error_code(-10025, domain="sdk")

        assert "FAIL_FUNCTION_NOT_SUPPORT" in description
        assert "function is not supported" in description

    def test_raw_cgi_password_error_is_preferred_for_device_domain(
        self,
    ) -> None:
        infos = lookup_error_codes(-4, domain="device_cgi")

        assert infos[0].name == "CGI_ERROR_PASSWORD"
        assert infos[0].sdk_equivalent == -29
        assert any(info.name == "QVERR_PARAMETER" for info in infos)

    def test_unknown_error_is_explicit(self) -> None:
        assert describe_error_code(987654321) == "unknown vendor error code"

    def test_lt_compat_positive_response_code_is_described(self) -> None:
        description = describe_error_code(10, domain="lt_compat")

        assert "GLNK_AUTH_PROTOCOL_ERROR" in description
        assert "protocol error" in description

    def test_cloud_storage_error_is_described(self) -> None:
        description = describe_error_code(
            310101009,
            domain="cloud_storage",
        )

        assert "FAIL_CS_DEV_IS_NOT_FOUND" in description
        assert "device was not found" in description

import xml.etree.ElementTree as ET

import pytest

from quii_helper.cloud.authentication.responses import (
    parse_device_token_response,
    parse_login_response,
)
from quii_helper.support.errors import QuiiConnectionError


def _xml(text: str) -> ET.Element:
    return ET.fromstring(text)


class CloudAuthResponseTests:
    def test_parse_login_response_reads_header_session_and_content(
        self,
    ) -> None:
        parsed = parse_login_response(
            _xml(
                """
                <response>
                  <header>
                    <result>0</result>
                    <session><id> session-1 </id></session>
                  </header>
                  <content>
                    <account-id> account-1 </account-id>
                    <token> token-1 </token>
                    <expire> 3600 </expire>
                  </content>
                </response>
                """
            ),
            "<raw/>",
        )

        assert "session-1" == parsed["session_id"]
        assert "account-1" == parsed["account_id"]
        assert "token-1" == parsed["token"]
        assert "3600" == parsed["expire"]
        assert "<raw/>" == parsed["raw"]

    def test_parse_login_response_supports_legacy_session_text(self) -> None:
        parsed = parse_login_response(
            _xml(
                """
                <response>
                  <header><result>0</result><session>legacy</session></header>
                  <content />
                </response>
                """
            ),
            "",
        )

        assert "legacy" == parsed["session_id"]

    def test_parse_login_response_rejects_error_result(self) -> None:
        with pytest.raises(
            QuiiConnectionError, match="cloud login result: 101"
        ):
            parse_login_response(
                _xml(
                    """
                    <response>
                      <header><result>101</result></header>
                    </response>
                    """
                ),
                "",
            )

    def test_parse_device_token_response_reads_camel_case_fields(self) -> None:
        parsed = parse_device_token_response(
            _xml(
                """
                <response>
                  <header><result>0</result></header>
                  <content>
                    <deviceid> device-1 </deviceid>
                    <dataEncodeKey> key-1 </dataEncodeKey>
                    <dynamicPassword> password-1 </dynamicPassword>
                    <pwdExpired> false </pwdExpired>
                    <transparentBasedata> basedata-1 </transparentBasedata>
                    <authCode> auth-1 </authCode>
                    <defaultOutAuthCode> default-1 </defaultOutAuthCode>
                  </content>
                </response>
                """
            ),
            "raw-device",
        )

        assert "device-1" == parsed["device_id"]
        assert "key-1" == parsed["data_encode_key"]
        assert "password-1" == parsed["dynamic_password"]
        assert "false" == parsed["pwd_expired"]
        assert "basedata-1" == parsed["transparent_basedata"]
        assert "auth-1" == parsed["auth_code"]
        assert "default-1" == parsed["default_out_auth_code"]
        assert "raw-device" == parsed["raw"]

    def test_parse_device_token_response_supports_kebab_case_fields(
        self,
    ) -> None:
        parsed = parse_device_token_response(
            _xml(
                """
                <response>
                  <header><result>0</result></header>
                  <content>
                    <device-id> device-2 </device-id>
                    <data-encode-key> key-2 </data-encode-key>
                    <dynamic-password> password-2 </dynamic-password>
                    <password-expired> true </password-expired>
                    <transparent-basedata> basedata-2 </transparent-basedata>
                    <channel-num> 4 </channel-num>
                    <type> doorphone </type>
                    <model> Marilyn </model>
                    <is-hs-device> 1 </is-hs-device>
                    <from-share> 0 </from-share>
                    <share-mode> owner </share-mode>
                    <out-auth-code> auth-2 </out-auth-code>
                    <default-out-auth-code>
                      default-2
                    </default-out-auth-code>
                  </content>
                </response>
                """
            ),
            "",
        )

        assert "device-2" == parsed["device_id"]
        assert "key-2" == parsed["data_encode_key"]
        assert "password-2" == parsed["dynamic_password"]
        assert "true" == parsed["pwd_expired"]
        assert "basedata-2" == parsed["transparent_basedata"]
        assert "4" == parsed["channel_num"]
        assert "doorphone" == parsed["device_type"]
        assert "Marilyn" == parsed["model"]
        assert "1" == parsed["is_hs_device"]
        assert "0" == parsed["from_share"]
        assert "owner" == parsed["share_mode"]
        assert "auth-2" == parsed["auth_code"]
        assert "default-2" == parsed["default_out_auth_code"]

    def test_parse_device_token_response_rejects_missing_content(self) -> None:
        with pytest.raises(
            QuiiConnectionError,
            match="device-token response content not found",
        ):
            parse_device_token_response(
                _xml(
                    """
                    <response>
                      <header><result>0</result></header>
                    </response>
                    """
                ),
                "",
            )

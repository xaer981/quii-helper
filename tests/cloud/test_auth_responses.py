import unittest
import xml.etree.ElementTree as ET

from quii_helper.cloud.authentication.responses import (
    parse_device_token_response,
    parse_login_response,
)


def _xml(text: str) -> ET.Element:
    return ET.fromstring(text)


class CloudAuthResponseTests(unittest.TestCase):
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

        self.assertEqual("session-1", parsed["session_id"])
        self.assertEqual("account-1", parsed["account_id"])
        self.assertEqual("token-1", parsed["token"])
        self.assertEqual("3600", parsed["expire"])
        self.assertEqual("<raw/>", parsed["raw"])

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

        self.assertEqual("legacy", parsed["session_id"])

    def test_parse_login_response_rejects_error_result(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "cloud login result: 101"):
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

        self.assertEqual("device-1", parsed["device_id"])
        self.assertEqual("key-1", parsed["data_encode_key"])
        self.assertEqual("password-1", parsed["dynamic_password"])
        self.assertEqual("false", parsed["pwd_expired"])
        self.assertEqual("basedata-1", parsed["transparent_basedata"])
        self.assertEqual("auth-1", parsed["auth_code"])
        self.assertEqual("default-1", parsed["default_out_auth_code"])
        self.assertEqual("raw-device", parsed["raw"])

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

        self.assertEqual("device-2", parsed["device_id"])
        self.assertEqual("key-2", parsed["data_encode_key"])
        self.assertEqual("password-2", parsed["dynamic_password"])
        self.assertEqual("true", parsed["pwd_expired"])
        self.assertEqual("basedata-2", parsed["transparent_basedata"])
        self.assertEqual("auth-2", parsed["auth_code"])
        self.assertEqual("default-2", parsed["default_out_auth_code"])

    def test_parse_device_token_response_rejects_missing_content(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "device-token response content not found",
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


if __name__ == "__main__":
    unittest.main()

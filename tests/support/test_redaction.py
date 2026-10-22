from quii_helper.config import RuntimeCredentials
from quii_helper.support.redaction import (
    REDACTED,
    redact_mapping,
    redact_xml_text,
)


class RedactionTests:
    def test_runtime_credentials_repr_hides_keys_and_raw_response(
        self,
    ) -> None:
        credentials = RuntimeCredentials(
            session_id="test-session-secret",
            dynamic_password="test-dynamic-secret",
            data_encode_key="test-media-secret",
            auth_code="test-auth-secret",
            transparent_basedata="test-opaque-secret",
            raw={"token": "test-raw-secret"},
        )
        assert "secret" not in repr(credentials)
        assert credentials.session_id == "test-session-secret"
        assert credentials.raw["token"] == "test-raw-secret"

    def test_redacts_alarm_sessions_and_private_resource_urls(self) -> None:
        redacted = redact_xml_text(
            "<header><session>private-session</session></header>"
            "<content><recordresurl>private-video</recordresurl>"
            "<recordsubresurl>private-image</recordsubresurl></content>"
        )
        assert "private-session" not in redacted
        assert "private-video" not in redacted
        assert "private-image" not in redacted
        assert redacted.count(REDACTED) == 3

    def test_redact_mapping_masks_sensitive_keys(self) -> None:
        assert redact_mapping(
            {
                "Cookie": "session=secret",
                "Content-Type": "application/xml",
                "Set-Cookie": "sid=secret",
                "X-Auth-Token": "token",
                "password": "secret",
            }
        ) == {
            "Cookie": REDACTED,
            "Content-Type": "application/xml",
            "Set-Cookie": REDACTED,
            "X-Auth-Token": REDACTED,
            "password": REDACTED,
        }

    def test_redact_xml_text_masks_sensitive_elements(self) -> None:
        redacted = redact_xml_text(
            "<content>"
            "<account>user@example.com</account>"
            "<password>secret</password>"
            "<dynamic-password>dyn</dynamic-password>"
            "<token>token</token>"
            "<safe>visible</safe>"
            "</content>"
        )

        assert "user@example.com" not in redacted
        assert "secret" not in redacted
        assert "<dynamic-password>[REDACTED]</dynamic-password>" in redacted
        assert "token</token>" not in redacted
        assert "<safe>visible</safe>" in redacted

from quii_helper.support.redaction import (
    REDACTED,
    redact_mapping,
    redact_xml_text,
)


class RedactionTests:
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

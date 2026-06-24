from typing import Any

from quii_helper.protocols.quii.url import build_quii_live_url
from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.probes.candidates import (
    QuiiCredentialCandidate,
    QuiiStreamCombo,
)


def build_tcp_probe_config_summary(
    *,
    token_result: dict[str, Any],
    probe_host: str,
    probe_port: int,
    combo_candidates: list[QuiiStreamCombo],
    credential_candidates: list[QuiiCredentialCandidate],
) -> dict[str, Any]:
    return {
        "host": probe_host,
        "port": probe_port,
        "use_forwarded_relay": settings.QUII_USE_FORWARDED_RELAY,
        "ap": settings.QUII_AP,
        "combo_candidates": [
            candidate.__dict__ for candidate in combo_candidates
        ],
        "key_len": len(token_result["data_encode_key"]),
        "credential_candidates": [
            {
                "username": item.username,
                "password_len": len(item.password),
                "label": item.label,
            }
            for item in credential_candidates
        ],
        "example_url": _example_url(
            probe_host=probe_host,
            probe_port=probe_port,
            combo_candidates=combo_candidates,
            credential_candidates=credential_candidates,
        ),
        "play_param": 1,
    }


def _example_url(
    *,
    probe_host: str,
    probe_port: int,
    combo_candidates: list[QuiiStreamCombo],
    credential_candidates: list[QuiiCredentialCandidate],
) -> str:
    if not credential_candidates or not combo_candidates:
        return ""
    return build_quii_live_url(
        credential_candidates[0].username,
        credential_candidates[0].password,
        probe_host,
        probe_port,
        channel=combo_candidates[0].channel,
        stream=combo_candidates[0].stream,
        ap=settings.QUII_AP,
        inner=settings.QUII_USE_INNER,
        newcn=combo_candidates[0].newcn,
    )

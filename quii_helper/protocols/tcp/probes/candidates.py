from dataclasses import dataclass
from typing import Any

from quii_helper.protocols.quii.url import build_quii_live_path
from quii_helper.protocols.tcp import settings


@dataclass(frozen=True)
class QuiiCredentialCandidate:
    username: str
    password: str
    label: str


@dataclass(frozen=True)
class QuiiStreamCombo:
    channel: int
    stream: int
    newcn: bool
    path: str


def probe_endpoint() -> tuple[str, int]:
    if settings.QUII_USE_FORWARDED_RELAY:
        return settings.QUII_RELAY_HOST, settings.QUII_RELAY_PORT
    return settings.QUII_HOST, settings.QUII_PORT


def credential_candidates(
    token_result: dict[str, Any],
) -> list[QuiiCredentialCandidate]:
    if settings.QUII_USE_FORWARDED_RELAY:
        candidates = [
            QuiiCredentialCandidate(
                username="adminapp",
                password=token_result.get("dynamic_password", ""),
                label="adminapp_dynamic_password",
            )
        ]
    else:
        candidates = [
            QuiiCredentialCandidate(
                username="adminapp",
                password=token_result.get("dynamic_password", ""),
                label="adminapp_dynamic_password",
            ),
            QuiiCredentialCandidate(
                username="adminapp2",
                password=token_result.get("auth_code", ""),
                label="adminapp2_auth_code_hash",
            ),
            QuiiCredentialCandidate(
                username="adminapp2",
                password=settings.AUTH_CODE,
                label="adminapp2_auth_code_raw",
            ),
        ]
    return [
        candidate
        for candidate in candidates
        if candidate.username and candidate.password
    ]


def combo_candidates() -> list[QuiiStreamCombo]:
    if settings.QUII_USE_FORWARDED_RELAY:
        return [
            QuiiStreamCombo(
                channel=settings.QUII_RELAY_CHANNEL,
                stream=settings.QUII_RELAY_STREAM,
                newcn=settings.QUII_RELAY_NEWCN,
                path=build_quii_live_path(
                    channel=settings.QUII_RELAY_CHANNEL,
                    stream=settings.QUII_RELAY_STREAM,
                    ap=settings.QUII_AP,
                    inner=settings.QUII_USE_INNER,
                    newcn=settings.QUII_RELAY_NEWCN,
                ),
            )
        ]
    return [
        QuiiStreamCombo(
            channel=channel,
            stream=stream,
            newcn=newcn,
            path=build_quii_live_path(
                channel=channel,
                stream=stream,
                ap=settings.QUII_AP,
                inner=settings.QUII_USE_INNER,
                newcn=newcn,
            ),
        )
        for channel in settings.QUII_CHANNEL_CANDIDATES
        for stream in settings.QUII_STREAM_CANDIDATES
        for newcn in settings.QUII_NEWCN_CANDIDATES
    ]

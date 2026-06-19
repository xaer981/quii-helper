from dataclasses import dataclass
from typing import Any

from quii_helper.io.paths import data_path
from quii_helper.media.writer import write_h264_stream
from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.client import QuiiClient
from quii_helper.protocols.tcp.probe_candidates import (
    QuiiCredentialCandidate,
    QuiiStreamCombo,
)
from quii_helper.protocols.tcp.probe_results import (
    tcp_probe_attempt_summary,
    tcp_probe_compact_summary,
    tcp_probe_error_summary,
)


@dataclass
class TcpProbeAttemptRunner:
    token_result: dict[str, Any]
    probe_host: str
    probe_port: int

    def run(
        self, *, combo: QuiiStreamCombo, credential: QuiiCredentialCandidate
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        client = self._create_client(combo=combo, credential=credential)
        try:
            result = client.probe_live(
                dump_file=self._dump_file(combo=combo, credential=credential),
                num_messages=settings.QUII_NUM_MESSAGES,
                play_param=1,
            )
            extracted = self._extract_stream(
                combo=combo, credential=credential, messages=result["messages"]
            )
            return (
                tcp_probe_attempt_summary(
                    combo=combo,
                    credential=credential,
                    result=result,
                    extracted=extracted,
                ),
                tcp_probe_compact_summary(
                    combo=combo,
                    credential=credential,
                    result=result,
                    extracted=extracted,
                ),
            )
        except Exception as exc:
            return (
                tcp_probe_error_summary(
                    combo=combo,
                    credential=credential,
                    exc=exc,
                    include_username=True,
                ),
                tcp_probe_error_summary(
                    combo=combo,
                    credential=credential,
                    exc=exc,
                    include_username=False,
                ),
            )
        finally:
            client.close()

    def _create_client(
        self, *, combo: QuiiStreamCombo, credential: QuiiCredentialCandidate
    ) -> QuiiClient:
        return QuiiClient(
            self.probe_host,
            self.probe_port,
            credential.username,
            credential.password,
            combo.path,
            self.token_result["data_encode_key"],
            use_inner=settings.QUII_USE_INNER,
        )

    def _dump_file(
        self, *, combo: QuiiStreamCombo, credential: QuiiCredentialCandidate
    ):
        dump_name = (
            f"quii_probe_ch{combo.channel}_st{combo.stream}"
            f"_nc{int(combo.newcn)}_{credential.label}.bin"
        )
        return data_path(dump_name.replace("@", "_"))

    def _extract_stream(
        self,
        *,
        combo: QuiiStreamCombo,
        credential: QuiiCredentialCandidate,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not settings.QUII_EXTRACT_STREAM:
            return None
        return write_h264_stream(
            f"quii_stream_ch{combo.channel}_st{combo.stream}"
            f"_nc{int(combo.newcn)}_{credential.label}".replace("@", "_"),
            messages,
            render_snapshot=settings.QUII_RENDER_SNAPSHOT,
            keep_raw_h264=settings.QUII_KEEP_RAW_H264,
        )

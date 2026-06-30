from typing import Any

from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.probes.attempt import TcpProbeAttemptRunner
from quii_helper.protocols.tcp.probes.candidates import (
    QuiiCredentialCandidate,
    QuiiStreamCombo,
    combo_candidates,
    credential_candidates,
    probe_endpoint,
)
from quii_helper.protocols.tcp.probes.config_summary import (
    build_tcp_probe_config_summary,
)
from quii_helper.protocols.tcp.probes.results import sort_compact_summary
from quii_helper.support.log import logger


class QuiiTcpProbeRunner:
    def run(self, token_result: dict[str, Any]) -> None:
        probe_host, probe_port = probe_endpoint()
        stream_combos = combo_candidates()
        credentials = credential_candidates(token_result)

        self._print_config(
            token_result=token_result,
            probe_host=probe_host,
            probe_port=probe_port,
            combo_candidates=stream_combos,
            credential_candidates=credentials,
        )

        if not settings.QUII_RUN_PROBE:
            logger.debug(
                "SKIPPED: set QUII_RUN_PROBE = True "
                "to attempt direct quii TCP probe"
            )
            return

        attempts, compact_summary = self._run_attempts(
            token_result=token_result,
            probe_host=probe_host,
            probe_port=probe_port,
            stream_combos=stream_combos,
            credentials=credentials,
        )
        sort_compact_summary(compact_summary)

        logger.debug("=== quii_summary ===")
        logger.debug("{}", compact_summary)
        if settings.QUII_PRINT_FULL_PROBE:
            logger.debug("=== quii_probe ===")
            logger.debug("{}", attempts)

    def _print_config(
        self,
        *,
        token_result: dict[str, Any],
        probe_host: str,
        probe_port: int,
        combo_candidates: list[QuiiStreamCombo],
        credential_candidates: list[QuiiCredentialCandidate],
    ) -> None:
        logger.debug("=== quii_config ===")
        logger.debug(
            "{}",
            build_tcp_probe_config_summary(
                token_result=token_result,
                probe_host=probe_host,
                probe_port=probe_port,
                combo_candidates=combo_candidates,
                credential_candidates=credential_candidates,
            ),
        )

    def _run_attempts(
        self,
        *,
        token_result: dict[str, Any],
        probe_host: str,
        probe_port: int,
        stream_combos: list[QuiiStreamCombo],
        credentials: list[QuiiCredentialCandidate],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        attempt_runner = TcpProbeAttemptRunner(
            token_result=token_result,
            probe_host=probe_host,
            probe_port=probe_port,
        )
        attempts: list[dict[str, Any]] = []
        compact_summary: list[dict[str, Any]] = []
        for combo in stream_combos:
            for credential in credentials:
                attempt, compact = attempt_runner.run(
                    combo=combo, credential=credential
                )
                attempts.append(attempt)
                compact_summary.append(compact)
        return attempts, compact_summary


def run_quii_probe(token_result: dict[str, Any]) -> None:
    QuiiTcpProbeRunner().run(token_result)

from typing import Any

from quii_helper.cloud import get_device_token, login_cloud
from quii_helper.config import AutonomousConfig, validate_camera_app_config
from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.probes.quii_probe import QuiiTcpProbeRunner
from quii_helper.support.log import logger


class CloudProbeFlow:
    def __init__(
        self, quii_probe_runner: QuiiTcpProbeRunner | None = None
    ) -> None:
        self.quii_probe_runner = quii_probe_runner or QuiiTcpProbeRunner()

    def run(self) -> None:
        config = AutonomousConfig()
        validate_camera_app_config(config)
        if not settings.CLOUD_ACCOUNT or not settings.CLOUD_PASSWORD:
            logger.debug("=== cloud_login ===")
            logger.debug(
                "SKIPPED: fill CLOUD_ACCOUNT and CLOUD_PASSWORD first"
            )
            return

        login_result = login_cloud(
            settings.CLOUD_ACCOUNT,
            settings.CLOUD_PASSWORD,
            auth_url=config.auth_url,
            ip_region_id=config.ip_region_id,
            client_id=config.client_id,
            oem=config.oem,
            app_id=config.app_id,
            client_type=config.client_type,
            debug=True,
        )
        logger.debug("=== cloud_login_parsed ===")
        logger.debug("{}", self._redact_raw(login_result))

        if not login_result["session_id"]:
            logger.debug("SKIPPED: session_id is empty")
            return

        if not settings.DEVICE_ID:
            logger.debug("=== get_device_token ===")
            logger.debug("SKIPPED: fill DEVICE_ID first")
            return

        token_result = get_device_token(
            login_result["session_id"],
            settings.DEVICE_ID,
            auth_url=config.auth_url,
            is_hs_device=settings.IS_HS_DEVICE,
            client_id=config.client_id,
            oem=config.oem,
            app_id=config.app_id,
            client_type=config.client_type,
            debug=True,
        )
        logger.debug("=== get_device_token_parsed ===")
        logger.debug("{}", self._redact_raw(token_result))

        self.quii_probe_runner.run(token_result)

    def _redact_raw(self, result: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in result.items() if key != "raw"}


def run_cloud_flow() -> None:
    CloudProbeFlow().run()

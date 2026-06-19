from typing import Any

from quii_helper.cloud import get_device_token, login_cloud
from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.quii_probe import QuiiTcpProbeRunner


class CloudProbeFlow:
    def __init__(
        self, quii_probe_runner: QuiiTcpProbeRunner | None = None
    ) -> None:
        self.quii_probe_runner = quii_probe_runner or QuiiTcpProbeRunner()

    def run(self) -> None:
        if not settings.CLOUD_ACCOUNT or not settings.CLOUD_PASSWORD:
            print("\n=== cloud_login ===")
            print("SKIPPED: fill CLOUD_ACCOUNT and CLOUD_PASSWORD first")
            return

        login_result = login_cloud(
            settings.CLOUD_ACCOUNT, settings.CLOUD_PASSWORD, debug=True
        )
        print("\n=== cloud_login_parsed ===")
        print(self._redact_raw(login_result))

        if not login_result["session_id"]:
            print("SKIPPED: session_id is empty")
            return

        if not settings.DEVICE_ID:
            print("\n=== get_device_token ===")
            print("SKIPPED: fill DEVICE_ID first")
            return

        token_result = get_device_token(
            login_result["session_id"],
            settings.DEVICE_ID,
            is_hs_device=settings.IS_HS_DEVICE,
            debug=True,
        )
        print("\n=== get_device_token_parsed ===")
        print(self._redact_raw(token_result))

        self.quii_probe_runner.run(token_result)

    def _redact_raw(self, result: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in result.items() if key != "raw"}


def run_cloud_flow() -> None:
    CloudProbeFlow().run()

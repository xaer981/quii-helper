from quii_helper.cloud.flows.probe_flow import CloudProbeFlow, run_cloud_flow
from quii_helper.device.probes.flow import (
    DeviceCgiProbeRunner,
    probe_mode,
    try_mode,
)
from quii_helper.protocols.tcp import settings
from quii_helper.protocols.tcp.probes.quii_probe import (
    QuiiTcpProbeRunner,
    run_quii_probe,
)
from quii_helper.protocols.tcp.probes.settings import (
    AUTH_CODE,
    CLOUD_ACCOUNT,
    CLOUD_PASSWORD,
    DEVICE_ID,
    DEVICE_PASSWORD,
    HOST,
    IS_HS_DEVICE,
    NC,
    QUII_AP,
    QUII_CHANNEL_CANDIDATES,
    QUII_EXTRACT_STREAM,
    QUII_HOST,
    QUII_KEEP_RAW_H264,
    QUII_NEWCN_CANDIDATES,
    QUII_NUM_MESSAGES,
    QUII_PORT,
    QUII_PRINT_FULL_PROBE,
    QUII_RELAY_CHANNEL,
    QUII_RELAY_HOST,
    QUII_RELAY_NEWCN,
    QUII_RELAY_PORT,
    QUII_RELAY_STREAM,
    QUII_RENDER_SNAPSHOT,
    QUII_RUN_PROBE,
    QUII_STREAM_CANDIDATES,
    QUII_USE_FORWARDED_RELAY,
    QUII_USE_INNER,
    RUN_CLOUD_FLOW,
    RUN_DEVICE_CGI_PROBES,
)


class TcpProbeRunner:
    def __init__(
        self,
        *,
        device_probe_runner: DeviceCgiProbeRunner | None = None,
        cloud_probe_flow: CloudProbeFlow | None = None,
    ) -> None:
        self.device_probe_runner = (
            device_probe_runner or DeviceCgiProbeRunner()
        )
        self.cloud_probe_flow = cloud_probe_flow or CloudProbeFlow(
            QuiiTcpProbeRunner()
        )

    def run(self) -> None:
        if settings.RUN_DEVICE_CGI_PROBES:
            self.device_probe_runner.run()

        if settings.RUN_CLOUD_FLOW:
            self.cloud_probe_flow.run()


__all__ = [
    "TcpProbeRunner",
    "run_cloud_flow",
    "run_quii_probe",
    "try_mode",
    "probe_mode",
    "AUTH_CODE",
    "CLOUD_ACCOUNT",
    "CLOUD_PASSWORD",
    "DEVICE_ID",
    "DEVICE_PASSWORD",
    "HOST",
    "IS_HS_DEVICE",
    "NC",
    "QUII_AP",
    "QUII_CHANNEL_CANDIDATES",
    "QUII_EXTRACT_STREAM",
    "QUII_HOST",
    "QUII_KEEP_RAW_H264",
    "QUII_NEWCN_CANDIDATES",
    "QUII_NUM_MESSAGES",
    "QUII_PORT",
    "QUII_PRINT_FULL_PROBE",
    "QUII_RELAY_CHANNEL",
    "QUII_RELAY_HOST",
    "QUII_RELAY_NEWCN",
    "QUII_RELAY_PORT",
    "QUII_RELAY_STREAM",
    "QUII_RENDER_SNAPSHOT",
    "QUII_RUN_PROBE",
    "QUII_STREAM_CANDIDATES",
    "QUII_USE_FORWARDED_RELAY",
    "QUII_USE_INNER",
    "RUN_CLOUD_FLOW",
    "RUN_DEVICE_CGI_PROBES",
]

from quii_helper.device.cgi import request_cgi, request_streamkey
from quii_helper.device.probe_modes import (
    fallback_streamkey_modes,
    primary_streamkey_mode,
    status_probe_kwargs,
)


class DeviceCgiProbeRunner:
    def run(self) -> None:
        self.probe_mode(
            "probe_device_status_lan",
            command="get.device.status",
            **status_probe_kwargs(),
        )

        primary_name, primary_kwargs = primary_streamkey_mode()
        if self.try_mode(primary_name, **primary_kwargs):
            return

        self._run_fallback_modes()

    def try_mode(self, name: str, **kwargs) -> bool:
        print(f"\n=== {name} ===")
        try:
            secret = request_streamkey(debug=True, **kwargs)
            print("SUCCESS:", secret)
            return True
        except Exception as exc:
            print("FAILED:", exc)
            return False

    def probe_mode(self, name: str, command: str, **kwargs) -> bool:
        print(f"\n=== {name} ===")
        try:
            result = request_cgi(command=command, debug=True, **kwargs)
            print("RESULT ERROR:", result["error"])
            return True
        except Exception as exc:
            print("FAILED:", exc)
            return False

    def _run_fallback_modes(self) -> None:
        for name, kwargs in fallback_streamkey_modes():
            self.try_mode(name, **kwargs)


def try_mode(name: str, **kwargs) -> bool:
    return DeviceCgiProbeRunner().try_mode(name, **kwargs)


def probe_mode(name: str, command: str, **kwargs) -> bool:
    return DeviceCgiProbeRunner().probe_mode(name, command, **kwargs)

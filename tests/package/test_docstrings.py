import inspect

from quii_helper import (
    Camera,
    CameraDeviceAllInfo,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceProductInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceStorageInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
)
from quii_helper.camera.outputs.results import CameraCaptureResult
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.config import AutonomousConfig
from quii_helper.preview.pipeline.config import PreviewCaptureSettings

DOCUMENTED_OBJECTS = (
    Camera,
    Camera.__init__,
    Camera.capture,
    Camera.get_device_info,
    Camera.get_device_all_info,
    Camera.get_product_info,
    Camera.get_storage_info,
    Camera.get_time_info,
    Camera.get_wifi_list,
    Camera.get_screen_flip_info,
    Camera.get_video_switch_info,
    Camera.get_time_title_info,
    Camera.get_network_info,
    Camera.get_system_general_info,
    Camera.get_system_capabilities,
    Camera.get_video_config,
    Camera.snapshot,
    Camera.save_video,
    Camera.record,
    Camera.serve_rtsp,
    CameraCaptureResult,
    CameraCaptureResult.from_summary,
    CameraCaptureResult.require_snapshot,
    CameraCaptureResult.require_video,
    CameraDeviceAllInfo,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceProductInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceStorageInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
    CameraRtspStream,
    CameraRtspStream.start,
    CameraRtspStream.wait,
    CameraRtspStream.close,
    AutonomousConfig,
    PreviewCaptureSettings,
)


class PublicDocstringTests:
    def test_high_level_api_has_docstrings(self) -> None:
        missing = [
            obj.__qualname__
            for obj in DOCUMENTED_OBJECTS
            if not inspect.getdoc(obj)
        ]
        assert [] == missing

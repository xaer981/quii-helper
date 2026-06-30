import importlib

import quii_helper

ROOT_PUBLIC_API = [
    "AssetMissingError",
    "AutonomousConfig",
    "Camera",
    "CameraCaptureError",
    "CameraCaptureResult",
    "ConfigurationError",
    "MediaRenderError",
    "PreviewCaptureSettings",
    "QuiiConnectionError",
    "QuiiHelperError",
    "RuntimeCredentials",
]

ROOT_INTERNAL_NAMES = [
    "CameraConnector",
    "CameraPreviewApplication",
    "CameraPreviewSession",
    "DirectKcpQuiiTunnel",
    "MqttP2PBootstrap",
    "P2PConnectRequest",
    "P2PConnectResponse",
    "PreviewArtifactManager",
    "PreviewCapturePipeline",
    "PreviewOutputWriter",
    "PreviewPacketProcessor",
    "PreviewPipelineFactory",
    "QuiiClient",
    "RbUdpQuiiTunnel",
    "TcpLiveProbeCapture",
    "TcpProbeRunner",
    "TcpSocketTransport",
    "TunnelPacketStream",
    "aes_cbc_crypt",
    "assemble_h264_stream_from_messages",
    "build_live_keepalive_packet",
    "build_live_play_packet",
    "build_live_setup_packet",
    "create_request_session_id",
    "create_session_flag",
    "decode_quii_blob",
    "open_direct_preview",
    "write_h264_stream",
]

EXPORT_PACKAGES = (
    "quii_helper",
    "quii_helper.cloud",
    "quii_helper.device",
    "quii_helper.diagnostics",
    "quii_helper.diagnostics.wrapped",
    "quii_helper.devtools",
    "quii_helper.direct",
    "quii_helper.io",
    "quii_helper.media",
    "quii_helper.preview",
    "quii_helper.protocols",
    "quii_helper.protocols.mqtt",
    "quii_helper.protocols.p2p",
    "quii_helper.protocols.quii",
    "quii_helper.protocols.rbudp",
    "quii_helper.protocols.tcp",
    "quii_helper.protocols.ust",
    "quii_helper.streaming",
    "quii_helper.streaming.h264",
    "quii_helper.streaming.rtp",
    "quii_helper.streaming.rtsp",
)


class PublicApiTests:
    def test_root_exported_symbols_import(self) -> None:
        failures = []
        for name in quii_helper.__all__:
            try:
                getattr(quii_helper, name)
            except Exception as exc:  # pragma: no cover - failure details
                failures.append((name, type(exc).__name__, str(exc)))

        assert [] == failures

    def test_root_all_matches_static_public_api(self) -> None:
        assert ROOT_PUBLIC_API == quii_helper.__all__

    def test_export_packages_import_all_symbols(self) -> None:
        failures = []
        for package_name in EXPORT_PACKAGES:
            package = importlib.import_module(package_name)
            for name in package.__all__:
                try:
                    getattr(package, name)
                except Exception as exc:  # pragma: no cover - failure details
                    failures.append(
                        (package_name, name, type(exc).__name__, str(exc))
                    )

        assert [] == failures

    def test_root_package_uses_static_exports(self) -> None:
        assert not hasattr(quii_helper, "__getattr__")

    def test_root_package_does_not_export_internal_api(self) -> None:
        for name in ROOT_INTERNAL_NAMES:
            assert not hasattr(quii_helper, name)

    def test_camera_high_level_methods_exist(self) -> None:
        camera_cls = quii_helper.Camera
        for method_name in (
            "capture",
            "snapshot",
            "save_video",
            "record",
            "serve_rtsp",
        ):
            assert callable(getattr(camera_cls, method_name, None))

"""Application package for QUII camera helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DATA_DIR": ("quii_helper.io.paths", "DATA_DIR"),
    "DirectKcpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "DirectKcpQuiiTunnel",
    ),
    "AutonomousConfig": ("quii_helper.config", "AutonomousConfig"),
    "Camera": ("quii_helper.camera", "Camera"),
    "CameraCaptureError": ("quii_helper.camera", "CameraCaptureError"),
    "CameraCaptureResult": ("quii_helper.camera", "CameraCaptureResult"),
    "CameraConnector": ("quii_helper.camera", "CameraConnector"),
    "CameraPreviewSession": ("quii_helper.camera", "CameraPreviewSession"),
    "CameraPreviewApplication": (
        "quii_helper.preview.application",
        "CameraPreviewApplication",
    ),
    "MqttP2PBootstrap": (
        "quii_helper.protocols.mqtt.bootstrap",
        "MqttP2PBootstrap",
    ),
    "PreviewCapturePipeline": (
        "quii_helper.preview.capture_pipeline",
        "PreviewCapturePipeline",
    ),
    "PreviewArtifactManager": (
        "quii_helper.preview.artifacts",
        "PreviewArtifactManager",
    ),
    "PreviewCaptureSettings": (
        "quii_helper.preview.config",
        "PreviewCaptureSettings",
    ),
    "PreviewOutputWriter": (
        "quii_helper.preview.output_writer",
        "PreviewOutputWriter",
    ),
    "PreviewPacketProcessor": (
        "quii_helper.preview.packet_processor",
        "PreviewPacketProcessor",
    ),
    "PreviewPipelineFactory": (
        "quii_helper.preview.pipeline_factory",
        "PreviewPipelineFactory",
    ),
    "P2PConnectRequest": (
        "quii_helper.protocols.p2p.protocol",
        "P2PConnectRequest",
    ),
    "P2PConnectResponse": (
        "quii_helper.protocols.p2p.protocol",
        "P2PConnectResponse",
    ),
    "QuiiClient": ("quii_helper.protocols.tcp.client", "QuiiClient"),
    "RbUdpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "RbUdpQuiiTunnel",
    ),
    "RuntimeCredentials": ("quii_helper.config", "RuntimeCredentials"),
    "STREAM_HIGH_QUALITY": ("quii_helper.config", "STREAM_HIGH_QUALITY"),
    "STREAM_LOW_BANDWIDTH": ("quii_helper.config", "STREAM_LOW_BANDWIDTH"),
    "TcpLiveProbeCapture": (
        "quii_helper.protocols.tcp.live_probe_capture",
        "TcpLiveProbeCapture",
    ),
    "TcpProbeRunner": ("quii_helper.protocols.tcp.runner", "TcpProbeRunner"),
    "TcpSocketTransport": (
        "quii_helper.protocols.tcp.transport",
        "TcpSocketTransport",
    ),
    "TunnelPacketStream": ("quii_helper.preview.stream", "TunnelPacketStream"),
    "aes_cbc_crypt": ("quii_helper.protocols.quii.crypto", "aes_cbc_crypt"),
    "assemble_h264_stream_from_messages": (
        "quii_helper.media.assembler",
        "assemble_h264_stream_from_messages",
    ),
    "build_live_keepalive_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_keepalive_packet",
    ),
    "build_live_play_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_play_packet",
    ),
    "build_live_setup_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_setup_packet",
    ),
    "create_request_session_id": (
        "quii_helper.protocols.p2p.protocol",
        "create_request_session_id",
    ),
    "create_session_flag": (
        "quii_helper.protocols.p2p.protocol",
        "create_session_flag",
    ),
    "decode_quii_blob": (
        "quii_helper.protocols.quii.blob",
        "decode_quii_blob",
    ),
    "open_direct_preview": (
        "quii_helper.direct.preview",
        "open_direct_preview",
    ),
    "resolve_stream_quality": (
        "quii_helper.config",
        "resolve_stream_quality",
    ),
    "resolve_data_path": ("quii_helper.io.paths", "resolve_data_path"),
    "timestamped_output_base": (
        "quii_helper.io.paths",
        "timestamped_output_base",
    ),
    "write_h264_stream": ("quii_helper.media.writer", "write_h264_stream"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value

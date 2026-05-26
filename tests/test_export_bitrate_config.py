"""剪映导出码率配置解析。"""
from __future__ import annotations

import config
from src.utils.video_task_manager import (
    _resolve_export_bitrate_kbps,
    _resolve_export_bitrate_mode_label,
    _resolve_export_bitrate_type,
)


def test_export_bitrate_config(monkeypatch) -> None:
    monkeypatch.setattr(config, "EXPORT_BITRATE_KBPS", 1000)
    monkeypatch.setattr(config, "EXPORT_BITRATE_TYPE", "VBR")
    monkeypatch.setattr(config, "EXPORT_BITRATE_MODE_UI_LABEL", "自定义")

    assert _resolve_export_bitrate_kbps() == 1000
    assert _resolve_export_bitrate_type() == "VBR"
    assert _resolve_export_bitrate_mode_label() == "自定义"

    monkeypatch.setattr(config, "EXPORT_BITRATE_KBPS", 0)
    assert _resolve_export_bitrate_kbps() is None

    monkeypatch.setattr(config, "EXPORT_BITRATE_TYPE", "invalid")
    assert _resolve_export_bitrate_type() == "VBR"

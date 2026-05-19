"""auto_render：仅测试 video_infos 时间轴拼接逻辑。"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

os.environ.setdefault("ENABLE_APIKEY", "false")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.schemas.auto_render import AutoRenderRequest, VideoClipInput
from src.service.auto_render import _build_video_infos_json


def test_build_two_clips_default_dissolve() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4", use_full_duration=True),
            VideoClipInput(video_url="http://example.com/b.mp4", use_full_duration=True),
        ],
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        raw = _build_video_infos_json(req)
    data = json.loads(raw)
    assert len(data) == 2
    assert data[0]["transition"] == "叠化"
    assert data[0]["transition_duration"] == 1_000_000
    assert "transition" not in data[1]


def test_build_custom_transition() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4", use_full_duration=True),
            VideoClipInput(video_url="http://example.com/b.mp4", use_full_duration=True),
        ],
        default_transition="3D空间",
        default_transition_duration=1_500_000,
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        raw = _build_video_infos_json(req)
    data = json.loads(raw)
    assert data[0]["transition"] == "3D空间"
    assert data[0]["transition_duration"] == 1_500_000


if __name__ == "__main__":
    test_build_two_clips_default_dissolve()
    test_build_custom_transition()
    print("ok")

"""auto_render：时间轴拼接与字幕时长校验。"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

os.environ.setdefault("ENABLE_APIKEY", "false")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from exceptions import CustomException
from src.schemas.auto_render import AutoRenderRequest, CaptionInput, VideoClipInput
from src.service.auto_render import (
    _build_video_infos_json,
    _validate_captions_timeline,
    compute_caption_transform_y_bottom,
    compute_timeline_duration_us,
)
from src.utils.video_probe import resolve_canvas_size


def _two_clip_request(**kwargs) -> AutoRenderRequest:
    return AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4", use_full_duration=True),
            VideoClipInput(video_url="http://example.com/b.mp4", use_full_duration=True),
        ],
        wait_export=False,
        **kwargs,
    )


def test_build_two_clips_default_dissolve() -> None:
    req = _two_clip_request()
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        raw = _build_video_infos_json(req, 25)
    data = json.loads(raw)
    assert len(data) == 2
    assert data[0]["transition"] == "叠化"
    assert data[0]["transition_duration"] == 1_000_000
    assert "transition" not in data[1]
    assert data[0]["start"] == 0
    assert data[0]["end"] == 10_000_000
    assert data[1]["start"] == 9_000_000
    assert data[1]["end"] == 19_000_000


def test_compute_timeline_duration_us() -> None:
    req = _two_clip_request()
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        assert compute_timeline_duration_us(req, 25) == 19_000_000


def test_validate_captions_timeline_ok() -> None:
    timeline = 19_000_000
    captions = [
        CaptionInput(text="a", start=0, end=9_500_000),
        CaptionInput(text="b", start=9_500_000, end=timeline),
    ]
    _validate_captions_timeline(captions, timeline, 25)


def test_validate_captions_timeline_gap() -> None:
    timeline = 19_000_000
    captions = [
        CaptionInput(text="a", start=0, end=9_000_000),
        CaptionInput(text="b", start=10_000_000, end=timeline),
    ]
    try:
        _validate_captions_timeline(captions, timeline, 25)
        raise AssertionError("expected CustomException")
    except CustomException as exc:
        assert "字幕总时长" in exc.detail


def test_validate_captions_timeline_wrong_end() -> None:
    captions = [CaptionInput(text="a", start=0, end=18_000_000)]
    try:
        _validate_captions_timeline(captions, 19_000_000, 25)
        raise AssertionError("expected CustomException")
    except CustomException as exc:
        assert "成片时长" in exc.detail


def test_validate_captions_timeline_wrong_start() -> None:
    captions = [CaptionInput(text="a", start=100_000, end=19_000_000)]
    try:
        _validate_captions_timeline(captions, 19_000_000, 25)
        raise AssertionError("expected CustomException")
    except CustomException as exc:
        assert "第一条字幕 start" in exc.detail


def test_compute_caption_transform_y_bottom() -> None:
    y = compute_caption_transform_y_bottom(1080, bottom_margin_px=10, font_size=15)
    assert y < 0
    assert -900 < y < -800
    y_small = compute_caption_transform_y_bottom(420, bottom_margin_px=10, font_size=15)
    assert y_small < 0
    assert -350 < y_small < -280


def test_build_custom_transition() -> None:
    req = _two_clip_request(
        default_transition="3D空间",
        default_transition_duration=1_500_000,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        raw = _build_video_infos_json(req, 25)
    data = json.loads(raw)
    assert data[0]["transition"] == "3D空间"
    assert data[0]["transition_duration"] == 1_500_000


def test_resolve_canvas_fallback() -> None:
    w, h = resolve_canvas_size([], width=1280, height=720, use_source=False)
    assert w == 1280 and h == 720


if __name__ == "__main__":
    test_build_two_clips_default_dissolve()
    test_compute_timeline_duration_us()
    test_validate_captions_timeline_ok()
    test_validate_captions_timeline_gap()
    test_validate_captions_timeline_wrong_end()
    test_validate_captions_timeline_wrong_start()
    test_compute_caption_transform_y_bottom()
    test_build_custom_transition()
    test_resolve_canvas_fallback()
    print("ok")

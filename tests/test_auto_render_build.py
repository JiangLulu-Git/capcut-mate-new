"""auto_render：时间轴拼接、画中画、背景图与字幕时长校验。"""
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
from src.schemas.auto_render import (
    AutoRenderRequest,
    CaptionInput,
    ImageClipInput,
    VideoClipInput,
)
from src.schemas.add_videos import SegmentInfo
from src.schemas.auto_render import CaptionInput
from src.service.auto_render import (
    _build_background_image_items,
    _build_overlay_exit_keyframes,
    _build_video_infos_json,
    _build_video_timeline_items,
    _clip_needs_overlay_exit_animation,
    _collect_timeline_captions,
    _validate_captions_timeline,
    compute_caption_transform_y_bottom,
    compute_timeline_duration_us,
)
from src.utils.video_probe import resolve_canvas_size

def _two_clip_request(**kwargs) -> AutoRenderRequest:
    return AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                use_full_duration=True,
                transition="叠化",
                transition_duration=1_000_000,
            ),
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


def test_validate_captions_timeline_ok_partial_coverage() -> None:
    """允许片尾无字幕、中间留空。"""
    timeline = 19_000_000
    captions = [
        CaptionInput(text="a", start=0, end=9_000_000),
        CaptionInput(text="b", start=10_000_000, end=15_000_000),
    ]
    _validate_captions_timeline(captions, timeline, 25)


def test_validate_captions_timeline_late_start_ok() -> None:
    timeline = 19_000_000
    captions = [CaptionInput(text="a", start=500_000, end=5_000_000)]
    _validate_captions_timeline(captions, timeline, 25)


def test_validate_captions_timeline_overlap() -> None:
    timeline = 19_000_000
    captions = [
        CaptionInput(text="a", start=0, end=10_000_000),
        CaptionInput(text="b", start=9_500_000, end=timeline),
    ]
    try:
        _validate_captions_timeline(captions, timeline, 25)
        raise AssertionError("expected CustomException")
    except CustomException as exc:
        assert "重叠" in exc.detail


def test_validate_captions_timeline_exceeds_timeline() -> None:
    captions = [CaptionInput(text="a", start=0, end=20_000_000)]
    try:
        _validate_captions_timeline(captions, 19_000_000, 25)
        raise AssertionError("expected CustomException")
    except CustomException as exc:
        assert "不能超过成片时长" in exc.detail


def test_compute_caption_transform_y_bottom() -> None:
    y = compute_caption_transform_y_bottom(1080, bottom_margin_px=10, font_size=15)
    assert y < 0
    assert -900 < y < -800
    y_lower = compute_caption_transform_y_bottom(
        1080, bottom_margin_px=10, font_size=15, offset_down_px=40
    )
    assert y_lower < y
    y_small = compute_caption_transform_y_bottom(420, bottom_margin_px=10, font_size=15)
    assert y_small < 0
    assert -350 < y_small < -280


def test_build_custom_transition() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                use_full_duration=True,
                transition="3D空间",
                transition_duration=1_500_000,
            ),
            VideoClipInput(video_url="http://example.com/b.mp4", use_full_duration=True),
        ],
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        raw = _build_video_infos_json(req, 25)
    data = json.loads(raw)
    assert data[0]["transition"] == "3D空间"
    assert data[0]["transition_duration"] == 1_500_000


def test_transitions_cycle_mode() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4"),
            VideoClipInput(video_url="http://example.com/b.mp4"),
            VideoClipInput(video_url="http://example.com/c.mp4"),
        ],
        transitions=["叠化", "3D空间"],
        transition_assign_mode="cycle",
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        items = _build_video_timeline_items(req, 25)
    assert items[0]["transition"] == "叠化"
    assert items[1]["transition"] == "3D空间"
    assert "transition" not in items[2]


def test_per_clip_overlay_layout() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                scale_x=0.8,
                transform_x=-200,
            ),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=False),
        ],
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        items = _build_video_timeline_items(req, 25)
    assert items[0]["scale_x"] == 0.8
    assert items[0]["transform_x"] == -200
    assert items[1]["scale_x"] == 1.0
    assert items[1]["transform_x"] == 0


def test_no_transition_by_clip_flag() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                no_transition=True,
            ),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=False),
        ],
        default_transition="叠化",
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        items = _build_video_timeline_items(req, 25)
    assert "transition" not in items[0]
    assert items[0]["end"] == 10_000_000
    assert items[1]["start"] == 10_000_000
    assert items[1]["end"] == 20_000_000


def test_per_clip_transition_and_no_transition() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                transition="叠化",
            ),
            VideoClipInput(
                video_url="http://example.com/b.mp4",
                overlay=True,
                no_transition=True,
            ),
            VideoClipInput(video_url="http://example.com/c.mp4", overlay=False),
        ],
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        items = _build_video_timeline_items(req, 25)
    assert items[0]["transition"] == "叠化"
    assert items[0]["start"] == 0
    assert items[0]["end"] == 10_000_000
    assert items[1]["start"] == 9_000_000
    assert "transition" not in items[1]
    assert items[2]["start"] == 19_000_000
    assert items[2]["scale_x"] == 1.0


def test_overlay_exit_skipped_without_per_clip_duration() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4", overlay=True),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=False),
        ],
        wait_export=False,
    )
    segs = [SegmentInfo(id="seg-1", start=0, end=10_000_000)]
    assert _build_overlay_exit_keyframes(req, segs) == []


def test_clip_needs_overlay_exit_animation() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4", overlay=True),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=True),
            VideoClipInput(video_url="http://example.com/c.mp4", overlay=False),
        ],
        wait_export=False,
    )
    assert _clip_needs_overlay_exit_animation(req, 0) is False
    assert _clip_needs_overlay_exit_animation(req, 1) is True
    assert _clip_needs_overlay_exit_animation(req, 2) is False


def test_build_overlay_exit_keyframes_custom_duration() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                overlay_exit_duration_us=2_000_000,
            ),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=False),
        ],
        wait_export=False,
    )
    segs = [
        SegmentInfo(id="seg-1", start=0, end=10_000_000),
        SegmentInfo(id="seg-2", start=10_000_000, end=20_000_000),
    ]
    kfs = _build_overlay_exit_keyframes(req, segs)
    assert len(kfs) == 8
    assert kfs[0]["segment_id"] == "seg-1"
    assert kfs[0]["offset"] == 8_000_000


def test_build_overlay_exit_keyframes() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                overlay_exit_duration_us=1_500_000,
            ),
            VideoClipInput(video_url="http://example.com/b.mp4", overlay=False),
        ],
        wait_export=False,
    )
    segs = [
        SegmentInfo(id="seg-1", start=0, end=10_000_000),
        SegmentInfo(id="seg-2", start=10_000_000, end=20_000_000),
    ]
    kfs = _build_overlay_exit_keyframes(req, segs)
    assert len(kfs) == 8
    assert kfs[0]["segment_id"] == "seg-1"
    assert kfs[0]["offset"] == 8_500_000
    assert kfs[0]["value"] == 0.75
    assert kfs[1]["offset"] == 10_000_000
    assert kfs[1]["value"] == 1.0


def test_embedded_video_captions_offset() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                use_full_duration=False,
                start=0,
                end=10_000_000,
                captions=[
                    CaptionInput(text="a", start=0, end=3_000_000),
                    CaptionInput(text="b", start=3_000_000, end=10_000_000),
                ],
            ),
            VideoClipInput(
                video_url="http://example.com/b.mp4",
                use_full_duration=False,
                start=10_000_000,
                end=20_000_000,
                captions=[CaptionInput(text="c", start=0, end=5_000_000)],
            ),
        ],
        wait_export=False,
    )
    items = [
        {"start": 0, "end": 10_000_000},
        {"start": 10_000_000, "end": 20_000_000},
    ]
    merged = _collect_timeline_captions(req, items)
    assert len(merged) == 3
    assert merged[0].start == 0 and merged[0].end == 3_000_000
    assert merged[1].start == 3_000_000 and merged[1].end == 10_000_000
    assert merged[2].start == 10_000_000 and merged[2].end == 15_000_000


def test_background_images_auto_align() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url="http://example.com/a.mp4"),
            VideoClipInput(video_url="http://example.com/b.mp4"),
        ],
        background_images=[
            ImageClipInput(image_url="http://example.com/bg1.jpg", width=1920, height=1080),
            ImageClipInput(image_url="http://example.com/bg2.jpg", width=1920, height=1080),
        ],
        wait_export=False,
    )
    with patch("src.service.auto_render.probe_video_duration_us", return_value=10_000_000):
        video_items = _build_video_timeline_items(req, 25)
        images = _build_background_image_items(req.background_images, video_items)
    assert len(images) == 2
    assert images[0]["start"] == 0
    assert images[0]["end"] == 10_000_000
    assert images[1]["start"] == 10_000_000
    assert images[1]["end"] == 20_000_000


def test_resolve_canvas_fallback() -> None:
    w, h = resolve_canvas_size([], width=1280, height=720, use_source=False)
    assert w == 1280 and h == 720


if __name__ == "__main__":
    test_build_two_clips_default_dissolve()
    test_compute_timeline_duration_us()
    test_validate_captions_timeline_ok_partial_coverage()
    test_validate_captions_timeline_late_start_ok()
    test_validate_captions_timeline_overlap()
    test_validate_captions_timeline_exceeds_timeline()
    test_compute_caption_transform_y_bottom()
    test_build_custom_transition()
    test_transitions_cycle_mode()
    test_per_clip_overlay_layout()
    test_no_transition_by_clip_flag()
    test_per_clip_transition_and_no_transition()
    test_overlay_exit_skipped_without_per_clip_duration()
    test_clip_needs_overlay_exit_animation()
    test_build_overlay_exit_keyframes()
    test_build_overlay_exit_keyframes_custom_duration()
    test_embedded_video_captions_offset()
    test_background_images_auto_align()
    test_resolve_canvas_fallback()
    print("ok")

"""auto_render time_unit 毫秒入参换算。"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.schemas.auto_render import AutoRenderRequest, CaptionInput, VideoClipInput
from src.service.auto_render import normalize_auto_render_request_times


def test_normalize_ms_to_us() -> None:
    req = AutoRenderRequest(
        time_unit="ms",
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                overlay=True,
                transition="叠化",
                transition_duration=1000,
                overlay_exit_duration_us=1500,
                start=0,
                end=5000,
                captions=[CaptionInput(text="hi", start=0, end=3000)],
            ),
        ],
        wait_export=False,
    )
    norm = normalize_auto_render_request_times(req)
    assert norm.time_unit == "us"
    assert norm.videos[0].transition_duration == 1_000_000
    assert norm.videos[0].overlay_exit_duration_us == 1_500_000
    assert norm.videos[0].end == 5_000_000
    assert norm.videos[0].captions[0].end == 3_000_000


def test_us_unchanged() -> None:
    req = AutoRenderRequest(
        time_unit="us",
        videos=[VideoClipInput(video_url="http://example.com/a.mp4", transition_duration=1_000_000)],
        wait_export=False,
    )
    norm = normalize_auto_render_request_times(req)
    assert norm.videos[0].transition_duration == 1_000_000


if __name__ == "__main__":
    test_normalize_ms_to_us()
    test_us_unchanged()
    print("ok")

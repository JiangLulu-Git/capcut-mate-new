"""parse_video_data 应保留每段 scale/transform（画中画）。"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.service.add_videos import parse_video_data


def test_parse_video_data_keeps_layout_fields() -> None:
    raw = json.dumps(
        [
            {
                "video_url": "https://example.com/a.mp4",
                "start": 0,
                "end": 10_000_000,
                "scale_x": 0.75,
                "scale_y": 0.75,
                "transform_x": -280,
                "transform_y": 0,
            }
        ]
    )
    items = parse_video_data(raw)
    assert items[0]["scale_x"] == 0.75
    assert items[0]["transform_x"] == -280


if __name__ == "__main__":
    test_parse_video_data_keeps_layout_fields()
    print("ok")

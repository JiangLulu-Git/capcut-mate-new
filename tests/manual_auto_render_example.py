"""
本地示例：调用 auto_render 服务（不经过 HTTP 时可直调）。

仅构建草稿、不等待导出:
  python tests/manual_auto_render_example.py --no-export

完整流程（需剪映在首页、main.py 已启动且 ENABLE_APIKEY=false）:
  python tests/manual_auto_render_example.py --wait-export
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.schemas.auto_render import AutoRenderRequest, CaptionInput, VideoClipInput
from src.service.auto_render import auto_render

DEMO_VIDEO = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="auto_render 本地示例")
    parser.add_argument(
        "--wait-export",
        action="store_true",
        help="同步等待剪映导出（耗时较长）",
    )
    parser.add_argument(
        "--video-url",
        default=DEMO_VIDEO,
        help="MP4 地址，可传多个（重复传参）",
    )
    parser.add_argument(
        "--transition",
        default="3D空间",
        help="段间转场名称（多段视频时生效）",
    )
    args = parser.parse_args()

    # 示例：两段相同视频 + 字幕 + 转场（探测原片全长后时间轴首尾相接）
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(video_url=args.video_url, use_full_duration=True),
            VideoClipInput(video_url=args.video_url, use_full_duration=True),
        ],
        captions=[
            CaptionInput(text="第一段字幕", start=0, end=3_000_000),
            CaptionInput(
                text="第二段字幕",
                start=90_000_000,
                end=93_000_000,
                in_animation="渐显",
                in_animation_duration=500_000,
            ),
        ],
        default_transition=args.transition,
        default_transition_duration=1_500_000,
        wait_export=args.wait_export,
        api_base_url="http://127.0.0.1:30000",
    )

    result = auto_render(req)
    print("draft_id:", result.draft_id)
    print("draft_url:", result.draft_url)
    print("export:", result.export_status, result.progress)
    print("video_url:", result.video_url)
    print("message:", result.message)
    if result.error_message:
        print("error:", result.error_message)
    return 0 if result.export_status in ("completed", "skipped", "processing") else 1


if __name__ == "__main__":
    raise SystemExit(main())

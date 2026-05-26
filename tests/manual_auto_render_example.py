"""
本地示例：调用 auto_render 服务（不经过 HTTP 时可直调）。

仅构建草稿、不等待导出:
  python tests/manual_auto_render_example.py --no-export

完整流程（需剪映在首页、main.py 已启动且 ENABLE_APIKEY=false）:
  python tests/manual_auto_render_example.py --wait-export

叠化 5 秒、无字幕:
  python tests/manual_auto_render_example.py --wait-export --transition 叠化 --transition-duration-sec 5 --no-captions
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
from src.service.auto_render import auto_render, compute_timeline_duration_us
from src.utils.video_probe import resolve_workflow_fps

DEMO_VIDEO = "https://teststatic.xuesee.net/sfs/coursedesignpc/qq.mp4"


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
        default="叠化",
        help="段间转场名称（多段视频时生效）",
    )
    parser.add_argument(
        "--transition-duration-sec",
        type=float,
        default=1.0,
        help="转场时长（秒），例如 5 表示叠化 5 秒",
    )
    parser.add_argument(
        "--no-captions",
        action="store_true",
        help="不添加字幕，仅测视频与转场",
    )
    args = parser.parse_args()

    transition_us = int(round(args.transition_duration_sec * 1_000_000))
    video_urls = [args.video_url, args.video_url]
    workflow_fps = resolve_workflow_fps(video_urls)

    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url=video_urls[0],
                use_full_duration=True,
                transition=args.transition,
                transition_duration=transition_us,
            ),
            VideoClipInput(video_url=video_urls[1], use_full_duration=True),
        ],
        wait_export=args.wait_export,
        api_base_url="http://127.0.0.1:30000",
    )

    if not args.no_captions:
        timeline_us = compute_timeline_duration_us(req, workflow_fps)
        mid = timeline_us // 2
        seg2_dur = max(1, timeline_us - mid)
        req = req.model_copy(
            update={
                "videos": [
                    req.videos[0].model_copy(
                        update={
                            "captions": [
                                CaptionInput(text="第一段字幕", start=0, end=mid),
                            ]
                        }
                    ),
                    req.videos[1].model_copy(
                        update={
                            "captions": [
                                CaptionInput(
                                    text="第二段字幕",
                                    start=0,
                                    end=seg2_dur,
                                    in_animation="渐显",
                                    in_animation_duration=500_000,
                                ),
                            ]
                        }
                    ),
                ]
            }
        )

    result = auto_render(req)
    print("draft_id:", result.draft_id)
    print("draft_url:", result.draft_url)
    print("timeline_duration_us:", result.timeline_duration_us)
    print("export:", result.export_status, result.progress)
    print("video_url:", result.video_url)
    print("message:", result.message)
    if result.error_message:
        print("error:", result.error_message)
    return 0 if result.export_status in ("completed", "skipped", "processing") else 1


if __name__ == "__main__":
    raise SystemExit(main())

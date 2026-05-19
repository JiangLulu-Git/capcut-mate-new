"""
测试：创建草稿 → 添加两段相同在线视频（视频1结尾「3D空间」转场）→ 保存并复制到剪映默认草稿目录。

运行（项目根目录）:
  python tests/test_draft_two_videos_online.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config  # noqa: E402
import src.pyJianYingDraft as draft  # noqa: E402
from src.service.create_draft import create_draft  # noqa: E402
from src.service.save_draft import save_draft  # noqa: E402
from src.service.add_videos import add_videos  # noqa: E402
from src.utils import helper  # noqa: E402
from src.utils.download import download  # noqa: E402
from src.utils.draft_downloader import (  # noqa: E402
    update_material_paths,
    patch_draft_meta_info,
    trigger_directory_scan_with_robocopy,
)

# 两段视频使用同一地址
VIDEO_URL = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)

# 转场加在视频1末尾（剪映规则：转场挂在「前面」那段素材上）
TRANSITION_NAME = "3D空间"
TRANSITION_DURATION_US = 1_500_000  # 1.5 秒（该转场默认时长，视觉冲击较强）
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


def probe_video_duration_us(video_url: str) -> int:
    """下载一次并读取原视频全长（微秒），供时间轴与 assets 对齐。"""
    probe_dir = os.path.join(config.TEMP_DIR, "video_duration_probe")
    os.makedirs(probe_dir, exist_ok=True)
    local_path = download(url=video_url, save_dir=probe_dir)
    duration_us = draft.VideoMaterial(local_path).duration
    if duration_us <= 0:
        raise RuntimeError(f"无法解析视频时长: {video_url}")
    return duration_us


def build_video_infos(clip_duration_us: int) -> str:
    """每段在时间轴上使用原视频全长；转场写在视频1末尾。"""
    t0, t1 = 0, clip_duration_us
    t2 = clip_duration_us * 2
    return json.dumps(
        [
            {
                "video_url": VIDEO_URL,
                "start": t0,
                "end": t1,
                "duration": clip_duration_us,
                "transition": TRANSITION_NAME,
                "transition_duration": TRANSITION_DURATION_US,
                "volume": 1.0,
            },
            {
                "video_url": VIDEO_URL,
                "start": t1,
                "end": t2,
                "duration": clip_duration_us,
                "volume": 1.0,
            },
        ],
        ensure_ascii=False,
    )


def rewrite_json_paths(json_path: str, src_root: str, dst_root: str) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    src_prefix = os.path.normpath(src_root) + os.sep
    dst_prefix = os.path.normpath(dst_root) + os.sep
    data = update_material_paths(data, src_prefix, dst_prefix)
    data = update_material_paths(
        data, src_prefix.replace("\\", "/"), dst_prefix.replace("\\", "/")
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def install_to_jianying(draft_id: str, jianying_root: str | None = None) -> str:
    """将 output/draft 下的草稿复制到剪映默认草稿目录。"""
    target_root = os.path.normpath(jianying_root or config.DRAFT_SAVE_PATH)
    src_dir = os.path.join(config.DRAFT_DIR, draft_id)
    dst_dir = os.path.join(target_root, draft_id)

    if not os.path.isdir(src_dir):
        raise FileNotFoundError(f"草稿未保存: {src_dir}")

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)

    for name in ("draft_content.json", "draft_info.json"):
        path = os.path.join(dst_dir, name)
        if os.path.isfile(path):
            rewrite_json_paths(path, src_dir, dst_dir)

    patch_draft_meta_info(dst_dir, draft_id)

    trigger_directory_scan_with_robocopy(dst_dir)
    return dst_dir


def main() -> int:
    jianying_root = os.path.normpath(config.DRAFT_SAVE_PATH)
    print(f"在线视频: {VIDEO_URL}")
    print(f"剪映草稿目录: {jianying_root}")

    clip_duration_us = probe_video_duration_us(VIDEO_URL)
    print(f"原视频时长: {clip_duration_us / 1e6:.3f} 秒")

    draft_url = create_draft(width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
    draft_id = helper.get_url_param(draft_url, "draft_id")
    print(f"1. 已创建草稿: {draft_id}")

    video_infos = build_video_infos(clip_duration_us)
    print(
        f"2. 添加两段视频（各 {clip_duration_us / 1e6:.3f}s，转场: {TRANSITION_NAME}）…"
    )
    draft_url, track_id, _video_ids, segment_ids = add_videos(
        draft_url=draft_url,
        video_infos=video_infos,
    )[:4]
    print(f"   track_id={track_id}, segments={segment_ids}")

    save_draft(draft_url)
    print(f"3. 已保存: {os.path.join(config.DRAFT_DIR, draft_id)}")

    installed = install_to_jianying(draft_id, jianying_root)
    print(f"4. 已安装到剪映目录: {installed}")
    print("请打开剪映专业版查看该草稿。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

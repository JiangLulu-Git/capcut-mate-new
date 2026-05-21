"""根据草稿内源素材体积估算导出 MP4 的目标码率。"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

import config
from src.utils.logger import logger

_VIDEO_SUFFIXES = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv")


def _draft_video_assets_dir(draft_dir: str) -> str:
    return os.path.join(draft_dir, "assets", "videos")


def sum_source_video_bytes(draft_dir: str) -> int:
    """统计草稿 assets/videos 下源文件总字节数。"""
    video_dir = _draft_video_assets_dir(draft_dir)
    if not os.path.isdir(video_dir):
        return 0
    total = 0
    for name in os.listdir(video_dir):
        path = os.path.join(video_dir, name)
        if os.path.isfile(path) and name.lower().endswith(_VIDEO_SUFFIXES):
            total += os.path.getsize(path)
    return total


def probe_media_duration_sec(media_path: str) -> float:
    """用 ffprobe 读取媒体时长（秒）。"""
    ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
    ffprobe = "ffprobe"
    if ffmpeg.lower().endswith("ffmpeg.exe"):
        ffprobe = ffmpeg[:-10] + "ffprobe.exe"
    elif ffmpeg != "ffmpeg":
        ffprobe = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe" if os.name == "nt" else "ffprobe")

    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                media_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return max(0.0, float(proc.stdout.strip()))
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def estimate_video_bitrate_from_sources(
    draft_dir: str,
    export_duration_sec: float,
) -> Optional[int]:
    """
    按源素材总大小与成片时长估算目标视频码率（bps）。

    目标：成片体积 ≈ 源素材体积之和 × EXPORT_SIZE_RATIO。
    """
    if export_duration_sec <= 0:
        return None

    source_bytes = sum_source_video_bytes(draft_dir)
    if source_bytes <= 0:
        return None

    ratio = float(getattr(config, "EXPORT_SIZE_RATIO", 1.05))
    audio_bps = _parse_bitrate_str(os.getenv("EXPORT_MP4_AUDIO_BITRATE", "128k"))

    target_bits = int(source_bytes * 8 * ratio)
    video_bps = int(target_bits / export_duration_sec) - audio_bps

    floor_bps = int(getattr(config, "EXPORT_MATCH_QUALITY_FLOOR_BPS", 2_500_000))
    min_bps = int(getattr(config, "EXPORT_MATCH_MIN_VIDEO_BITRATE", 400_000))
    max_bps = int(getattr(config, "EXPORT_MATCH_MAX_VIDEO_BITRATE", 12_000_000))
    video_bps = max(floor_bps, min_bps, min(max_bps, video_bps))

    logger.info(
        "Source size match: draft=%s sources=%s bytes export=%.2fs "
        "target_video_bitrate=%s kbps (ratio=%s)",
        draft_dir,
        source_bytes,
        export_duration_sec,
        video_bps // 1000,
        ratio,
    )
    return video_bps


def _parse_bitrate_str(value: str) -> int:
    v = (value or "128k").strip().lower()
    if v.endswith("k"):
        return int(float(v[:-1]) * 1000)
    if v.endswith("m"):
        return int(float(v[:-1]) * 1_000_000)
    return int(v)

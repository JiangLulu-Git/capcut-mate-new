"""探测源视频帧率/时长，并与草稿、导出帧率对齐。"""
from __future__ import annotations

import json
import os
from typing import Optional, Tuple

import pymediainfo

import config
from src.utils.draft_cache import DRAFT_CACHE
from src.utils.download import download
from src.utils.logger import logger

_EXPORT_FPS_CHOICES = (24, 25, 30, 50, 60)


def normalize_export_fps(raw_fps: Optional[float]) -> int:
    """将探测帧率映射到剪映导出面板支持的整数 fps。"""
    if raw_fps is None or raw_fps <= 0:
        return int(config.EXPORT_FRAMERATE_FPS)
    return min(_EXPORT_FPS_CHOICES, key=lambda x: abs(x - raw_fps))


def probe_video_fps(local_path: str) -> Optional[float]:
    """从本地文件读取视频帧率（如 29.97）。"""
    if not pymediainfo.MediaInfo.can_parse():
        return None
    info = pymediainfo.MediaInfo.parse(
        os.path.abspath(local_path),
        mediainfo_options={"File_TestContinuousFileNames": "0"},
    )
    if not info.video_tracks:
        return None
    track = info.video_tracks[0]
    for attr in ("frame_rate", "framerate"):
        val = getattr(track, attr, None)
        if val:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def probe_video_fps_from_url(video_url: str, save_dir: str) -> Optional[float]:
    path = download(url=video_url, save_dir=save_dir)
    return probe_video_fps(path)


def _even_dim(value: int) -> int:
    """编码器通常要求宽高为偶数。"""
    v = max(2, int(value))
    return v - (v % 2)


def probe_video_dimensions(local_path: str) -> Optional[Tuple[int, int]]:
    """从本地文件读取视频宽高（像素）。"""
    if not pymediainfo.MediaInfo.can_parse():
        return None
    info = pymediainfo.MediaInfo.parse(
        os.path.abspath(local_path),
        mediainfo_options={"File_TestContinuousFileNames": "0"},
    )
    if not info.video_tracks:
        return None
    track = info.video_tracks[0]
    try:
        w = int(track.width)  # type: ignore[arg-type]
        h = int(track.height)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return _even_dim(w), _even_dim(h)


def probe_video_dimensions_from_url(video_url: str, save_dir: str) -> Optional[Tuple[int, int]]:
    path = download(url=video_url, save_dir=save_dir)
    return probe_video_dimensions(path)


def resolve_canvas_size(
    video_urls: list[str],
    *,
    width: Optional[int],
    height: Optional[int],
    use_source: bool = True,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> Tuple[int, int]:
    """
    决定草稿画布尺寸。
    use_source=True 时优先用第一段素材探测宽高；失败则用 width/height 或 1920×1080。
    """
    if use_source and video_urls:
        probe_dir = os.path.join(config.TEMP_DIR, "auto_render_probe")
        os.makedirs(probe_dir, exist_ok=True)
        dims = probe_video_dimensions_from_url(video_urls[0], probe_dir)
        if dims:
            logger.info(
                "Align canvas to source: url=%s size=%sx%s",
                video_urls[0][:80],
                dims[0],
                dims[1],
            )
            return dims

    if width and height and width > 0 and height > 0:
        return _even_dim(width), _even_dim(height)
    return _even_dim(fallback_width), _even_dim(fallback_height)


def snap_duration_us_to_fps(duration_us: int, fps: int) -> int:
    """将时长向下取整到整帧，避免时间轴末尾「多出来」的半帧停住。"""
    if fps <= 0 or duration_us <= 0:
        return duration_us
    frame_us = max(1, round(1_000_000 / fps))
    return max(frame_us, (duration_us // frame_us) * frame_us)


def apply_draft_fps(draft_id: str, fps: int) -> None:
    """同步草稿时间轴 fps（draft_content / draft_info）。"""
    if draft_id in DRAFT_CACHE:
        script = DRAFT_CACHE[draft_id]
        script.fps = fps
        if isinstance(script.content, dict):
            script.content["fps"] = fps

    for name in ("draft_content.json", "draft_info.json"):
        path = os.path.join(config.DRAFT_DIR, draft_id, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "fps" in data:
                data["fps"] = fps
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to update %s fps: %s", path, exc)


def resolve_workflow_fps(video_urls: list[str]) -> int:
    """
    决定本次成片使用的 fps：
    - EXPORT_ALIGN_SOURCE_FPS=true：用第一段素材探测帧率（对齐源片）
    - 否则：EXPORT_FRAMERATE_FPS
    """
    if not getattr(config, "EXPORT_ALIGN_SOURCE_FPS", True):
        return int(config.EXPORT_FRAMERATE_FPS)

    if not video_urls:
        return int(config.EXPORT_FRAMERATE_FPS)

    probe_dir = os.path.join(config.TEMP_DIR, "auto_render_probe")
    os.makedirs(probe_dir, exist_ok=True)
    raw = probe_video_fps_from_url(video_urls[0], probe_dir)
    fps = normalize_export_fps(raw)
    logger.info(
        "Align fps to source: url=%s raw_fps=%s workflow_fps=%s export_default=%s",
        video_urls[0][:80],
        raw,
        fps,
        config.EXPORT_FRAMERATE_FPS,
    )
    return fps


def read_draft_fps(draft_id: str) -> int:
    if draft_id in DRAFT_CACHE:
        return int(DRAFT_CACHE[draft_id].fps)
    path = os.path.join(config.DRAFT_DIR, draft_id, "draft_content.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(json.load(f).get("fps", config.EXPORT_FRAMERATE_FPS))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return int(config.EXPORT_FRAMERATE_FPS)

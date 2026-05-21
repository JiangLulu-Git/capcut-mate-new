"""导出 MP4 的 Web 播放优化（faststart / 高质量压缩）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

import config
from src.utils.logger import logger


def _resolve_compress_mode() -> str:
    mode = (getattr(config, "EXPORT_COMPRESS_MODE", None) or "").strip().lower()
    if mode in ("quality", "source_size", "off"):
        return mode
    if getattr(config, "EXPORT_MATCH_SOURCE_SIZE", False):
        return "source_size"
    return "quality"


def _resolve_match_source_bitrate(mp4_path: str, draft_id: Optional[str]) -> Optional[int]:
    if not draft_id:
        return None
    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    if not os.path.isdir(draft_dir):
        return None

    from src.utils.mp4_source_size import (
        estimate_video_bitrate_from_sources,
        probe_media_duration_sec,
    )

    duration_sec = probe_media_duration_sec(mp4_path)
    return estimate_video_bitrate_from_sources(draft_dir, duration_sec)


def _find_ffmpeg() -> str | None:
    path = os.getenv("FFMPEG_PATH", "ffmpeg")
    try:
        subprocess.run(
            [path, "-version"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return path
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _null_output() -> str:
    return "NUL" if os.name == "nt" else "/dev/null"


def _run_ffmpeg(cmd: List[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _encode_crf(
    ffmpeg: str,
    mp4_path: str,
    tmp_path: str,
    crf: str,
    preset: str,
    audio_bitrate: str,
    timeout: int,
) -> bool:
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        mp4_path,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-movflags",
        "+faststart",
        tmp_path,
    ]
    logger.info("MP4 quality compress: crf=%s preset=%s path=%s", crf, preset, mp4_path)
    proc = _run_ffmpeg(cmd, timeout)
    if proc.returncode != 0:
        logger.error(
            "ffmpeg CRF failed (code=%s): %s",
            proc.returncode,
            (proc.stderr or proc.stdout or "")[-2000:],
        )
        return False
    return True


def _encode_two_pass_bitrate(
    ffmpeg: str,
    mp4_path: str,
    tmp_path: str,
    video_bps: int,
    preset: str,
    audio_bitrate: str,
    timeout: int,
) -> bool:
    video_k = max(1, video_bps // 1000)
    max_k = max(video_k, int(video_k * 1.12))
    buf_k = max_k * 2
    passlog = tempfile.mktemp(prefix="ffmpeg2pass_", dir=os.path.dirname(mp4_path))
    base: List[str] = [
        ffmpeg,
        "-y",
        "-i",
        mp4_path,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-b:v",
        f"{video_k}k",
        "-maxrate",
        f"{max_k}k",
        "-bufsize",
        f"{buf_k}k",
    ]
    logger.info(
        "MP4 two-pass compress: video=%skbps preset=%s path=%s",
        video_k,
        preset,
        mp4_path,
    )
    half_timeout = max(120, timeout // 2)
    pass1 = _run_ffmpeg(
        base
        + [
            "-pass",
            "1",
            "-passlogfile",
            passlog,
            "-an",
            "-f",
            "mp4",
            _null_output(),
        ],
        half_timeout,
    )
    if pass1.returncode != 0:
        logger.error(
            "ffmpeg pass1 failed (code=%s): %s",
            pass1.returncode,
            (pass1.stderr or pass1.stdout or "")[-2000:],
        )
        _cleanup_passlog(passlog)
        return False

    pass2 = _run_ffmpeg(
        base
        + [
            "-pass",
            "2",
            "-passlogfile",
            passlog,
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            tmp_path,
        ],
        half_timeout,
    )
    _cleanup_passlog(passlog)
    if pass2.returncode != 0:
        logger.error(
            "ffmpeg pass2 failed (code=%s): %s",
            pass2.returncode,
            (pass2.stderr or pass2.stdout or "")[-2000:],
        )
        return False
    return True


def _cleanup_passlog(passlog: str) -> None:
    for suffix in ("", "-0.log", "-0.log.mbtree"):
        path = f"{passlog}{suffix}"
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _faststart_remux(ffmpeg: str, mp4_path: str, tmp_path: str, timeout: int) -> bool:
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        mp4_path,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        tmp_path,
    ]
    logger.info("MP4 faststart remux: %s", mp4_path)
    proc = _run_ffmpeg(cmd, timeout)
    if proc.returncode != 0:
        logger.error(
            "ffmpeg remux failed (code=%s): %s",
            proc.returncode,
            (proc.stderr or proc.stdout or "")[-2000:],
        )
        return False
    return True


def optimize_mp4_for_web(mp4_path: str, *, draft_id: Optional[str] = None) -> bool:
    """
    剪映导出后的二次处理：
    - quality（默认）：CRF 压缩，体积通常为直出的 30%～50%，观感接近
    - source_size：按源素材体积两遍编码（有码率下限，避免为省体积严重糊）
    - off：仅 faststart
    """
    if not getattr(config, "EXPORT_MP4_WEB_OPTIMIZE", True):
        return False
    if not mp4_path or not os.path.isfile(mp4_path):
        return False

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.warning(
            "未找到 ffmpeg，跳过 MP4 优化；请安装 ffmpeg 并加入 PATH，或设置 FFMPEG_PATH"
        )
        return False

    mode = _resolve_compress_mode()
    preset = getattr(config, "EXPORT_MP4_PRESET", None) or os.getenv("EXPORT_MP4_PRESET", "medium")
    audio = os.getenv("EXPORT_MP4_AUDIO_BITRATE", "128k")
    timeout = int(os.getenv("EXPORT_MP4_FFMPEG_TIMEOUT_SEC", "3600"))

    fd, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=os.path.dirname(mp4_path))
    os.close(fd)
    try:
        ok = False
        if mode == "off":
            ok = _faststart_remux(ffmpeg, mp4_path, tmp_path, timeout)
        elif mode == "source_size":
            target_bps = _resolve_match_source_bitrate(mp4_path, draft_id)
            if target_bps:
                ok = _encode_two_pass_bitrate(
                    ffmpeg, mp4_path, tmp_path, target_bps, preset, audio, timeout
                )
            else:
                crf = (getattr(config, "EXPORT_MP4_CRF", None) or "20").strip() or "20"
                ok = _encode_crf(ffmpeg, mp4_path, tmp_path, crf, preset, audio, timeout)
        else:
            crf = (getattr(config, "EXPORT_MP4_CRF", None) or "20").strip() or "20"
            ok = _encode_crf(ffmpeg, mp4_path, tmp_path, crf, preset, audio, timeout)

        if not ok:
            return False

        old_size = os.path.getsize(mp4_path)
        shutil.move(tmp_path, mp4_path)
        new_size = os.path.getsize(mp4_path)
        logger.info(
            "MP4 optimize done mode=%s: %s (%s -> %s bytes, %.1f%%)",
            mode,
            mp4_path,
            old_size,
            new_size,
            (new_size / old_size * 100) if old_size else 0,
        )
        return True
    except Exception as exc:
        logger.exception("MP4 web optimize error: %s", exc)
        return False
    finally:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

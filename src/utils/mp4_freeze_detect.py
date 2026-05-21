"""用 ffmpeg freezedetect 检测 MP4 中的画面冻结段。"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class FreezeSegment:
    start_sec: float
    end_sec: float
    duration_sec: float


_FREEZE_START = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_END = re.compile(r"freeze_end:\s*([\d.]+)\s*\|\s*duration:\s*([\d.]+)")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def detect_freeze_segments(
    mp4_path: str,
    *,
    noise_db: int = -60,
    min_duration_sec: float = 0.25,
    timeout_sec: int = 600,
) -> List[FreezeSegment]:
    """
    扫描整段视频，返回所有 freeze 区间（秒）。
    需本机 PATH 中有 ffmpeg。
    """
    if not ffmpeg_available():
        raise RuntimeError("未找到 ffmpeg，无法做卡顿检测")

    vf = f"freezedetect=n={noise_db}dB:d={min_duration_sec}"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        mp4_path,
        "-vf",
        vf,
        "-an",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
    )
    log = (proc.stderr or "") + (proc.stdout or "")
    segments: List[FreezeSegment] = []
    start: Optional[float] = None
    for line in log.splitlines():
        m_start = _FREEZE_START.search(line)
        if m_start:
            start = float(m_start.group(1))
            continue
        m_end = _FREEZE_END.search(line)
        if m_end and start is not None:
            end = float(m_end.group(1))
            dur = float(m_end.group(2))
            segments.append(FreezeSegment(start_sec=start, end_sec=end, duration_sec=dur))
            start = None
    return segments


def freezes_in_window(
    segments: List[FreezeSegment],
    window_start_sec: float,
    window_end_sec: float,
) -> List[FreezeSegment]:
    """返回与 [window_start, window_end] 有交集的 freeze 段。"""
    if window_end_sec <= window_start_sec:
        return []
    hits: List[FreezeSegment] = []
    for seg in segments:
        if seg.end_sec <= window_start_sec or seg.start_sec >= window_end_sec:
            continue
        hits.append(seg)
    return hits

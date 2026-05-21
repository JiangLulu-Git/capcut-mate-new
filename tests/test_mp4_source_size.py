"""源素材体积 → 目标码率估算。"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.mp4_source_size import estimate_video_bitrate_from_sources, sum_source_video_bytes


def test_estimate_bitrate_from_sources(tmp_path) -> None:
    video_dir = tmp_path / "assets" / "videos"
    video_dir.mkdir(parents=True)
    # 100MB 源
    (video_dir / "a.mp4").write_bytes(b"\x00" * (100 * 1024 * 1024))

    assert sum_source_video_bytes(str(tmp_path)) == 100 * 1024 * 1024

    # 估算约 1Mbps，但受画质下限 2.5Mbps 保护
    bps = estimate_video_bitrate_from_sources(str(tmp_path), 800.0)
    assert bps is not None
    assert bps >= 2_500_000


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        test_estimate_bitrate_from_sources(Path(d))
    print("ok")

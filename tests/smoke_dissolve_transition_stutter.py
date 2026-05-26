"""
叠化转场测试：时间轴重叠 +（可选）导出后在转场前几秒检测画面冻结。

另开终端，在 API 已启动后执行:

  python tests/smoke_dissolve_transition_stutter.py
  python tests/smoke_dissolve_transition_stutter.py --export
  python tests/smoke_dissolve_transition_stutter.py --export --transition-duration-sec 5

或:

  powershell -ExecutionPolicy Bypass -File .\\deploy\\test-dissolve-transition.ps1
  powershell -ExecutionPolicy Bypass -File .\\deploy\\test-dissolve-transition.ps1 -Export
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ENABLE_APIKEY", "false")

from src.schemas.auto_render import AutoRenderRequest, VideoClipInput
from src.service.auto_render import _build_video_infos_json, probe_video_duration_us
from src.utils.mp4_freeze_detect import (
    detect_freeze_segments,
    ffmpeg_available,
    freezes_in_window,
)
from src.utils.transition_timeline import overlap_transition_us

DEFAULT_BASE = os.getenv("SMOKE_API_BASE", "http://127.0.0.1:30000")
AUTO_RENDER_URL = f"{DEFAULT_BASE.rstrip('/')}/openapi/capcut-mate/v1/auto_render"
OPENAPI_URL = f"{DEFAULT_BASE.rstrip('/')}/openapi.json"

DEMO_VIDEO = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)

# 转场开始后检测的秒数（不超过实际转场时长）
CHECK_SEC_AFTER_TRANSITION_START = 3.0


def _wait_api(timeout_sec: float, openapi_url: str) -> None:
    deadline = time.time() + timeout_sec
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(openapi_url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(1.0)
    raise RuntimeError(f"等待 API 就绪超时 ({timeout_sec}s): {openapi_url}") from last_err


def _transition_check_window(
    video_infos: List[Dict[str, Any]],
    transition_name: str,
    transition_duration_us: int,
    workflow_fps: int,
) -> Tuple[float, float, float]:
    """
    返回 (transition_start_sec, window_end_sec, overlap_sec)。
    叠化为重叠转场： junction = 第一段 end；转场从 junction - overlap 开始。
    """
    if len(video_infos) < 2:
        raise ValueError("需要至少两段视频才能测段间叠化")
    overlap_us = overlap_transition_us(transition_name, transition_duration_us)
    if overlap_us <= 0:
        raise ValueError(f"转场 {transition_name!r} 非重叠转场，本脚本仅测叠化类重叠转场")

    junction_us = int(video_infos[0]["end"])
    overlap_sec = overlap_us / 1_000_000.0
    transition_start_sec = max(0.0, junction_us / 1_000_000.0 - overlap_sec)
    check_span = min(CHECK_SEC_AFTER_TRANSITION_START, overlap_sec)
    window_end_sec = transition_start_sec + check_span
    return transition_start_sec, window_end_sec, overlap_sec


def _check_timeline_build(
    video_url: str,
    transition: str,
    transition_duration_us: int,
    workflow_fps: int = 25,
) -> Tuple[List[Dict[str, Any]], Tuple[float, float]]:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url=video_url,
                use_full_duration=True,
                transition=transition,
                transition_duration=transition_duration_us,
            ),
            VideoClipInput(video_url=video_url, use_full_duration=True),
        ],
        wait_export=False,
    )
    with patch(
        "src.service.auto_render.probe_video_duration_us",
        side_effect=lambda url, fps: probe_video_duration_us(url, fps),
    ):
        raw = _build_video_infos_json(req, workflow_fps)
    data = json.loads(raw)
    assert data[0].get("transition") == transition
    assert data[1].get("transition") is None
    assert data[1]["start"] == data[0]["end"] - transition_duration_us
    win = _transition_check_window(data, transition, transition_duration_us, workflow_fps)
    return data, (win[0], win[1])


def _http_auto_render(
    auto_render_url: str, body: Dict[str, Any], timeout_sec: int
) -> Dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        auto_render_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _unwrap_api_data(resp: Dict[str, Any]) -> Dict[str, Any]:
    code = resp.get("code")
    if code is not None and code != 1:
        raise RuntimeError(resp.get("message") or f"API code={code}")
    if isinstance(resp.get("data"), dict):
        return resp["data"]
    return resp


def _download_mp4(video_url: str, dest: Path, timeout_sec: int = 300) -> None:
    req = urllib.request.Request(video_url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        dest.write_bytes(resp.read())


def _analyze_exported_mp4(
    mp4_path: str,
    window_start: float,
    window_end: float,
) -> List[Any]:
    segments = detect_freeze_segments(mp4_path)
    return freezes_in_window(segments, window_start, window_end)


def main() -> int:
    parser = argparse.ArgumentParser(description="叠化转场冒烟（时间轴 + 可选导出卡顿检测）")
    parser.add_argument(
        "--export",
        action="store_true",
        help="调用 auto_render 并等待剪映导出，再检测转场前几秒是否 freeze",
    )
    parser.add_argument("--api-base", default=DEFAULT_BASE, help="API 根地址")
    parser.add_argument("--video-url", default=DEMO_VIDEO)
    parser.add_argument("--transition", default="叠化")
    parser.add_argument("--transition-duration-sec", type=float, default=1.0)
    parser.add_argument("--export-timeout-sec", type=int, default=1800)
    parser.add_argument("--wait-api-sec", type=float, default=90.0)
    parser.add_argument("--skip-wait-api", action="store_true")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    auto_render_url = f"{api_base}/openapi/capcut-mate/v1/auto_render"
    openapi_url = f"{api_base}/openapi.json"

    if not args.skip_wait_api:
        print(f"等待 API: {openapi_url}")
        _wait_api(args.wait_api_sec, openapi_url)

    transition_us = int(round(args.transition_duration_sec * 1_000_000))
    from src.utils.video_probe import resolve_workflow_fps

    workflow_fps = resolve_workflow_fps([args.video_url])
    print(f"1/3 校验叠化时间轴重叠 (fps={workflow_fps})…")
    _infos, (win_start, win_end) = _check_timeline_build(
        args.video_url, args.transition, transition_us, workflow_fps
    )
    print(
        f"   时间轴 OK；转场检测窗口 [{win_start:.3f}s, {win_end:.3f}s] "
        f"(叠化 {args.transition_duration_sec}s)"
    )

    if not args.export:
        print("2/3 跳过导出（加 --export 可测成片转场前几秒卡顿）")
        print("3/3 通过（仅时间轴）")
        return 0

    if not ffmpeg_available():
        print("错误: --export 需要 ffmpeg（freezedetect）", file=sys.stderr)
        return 2

    body = {
        "videos": [
            {
                "video_url": args.video_url,
                "use_full_duration": True,
                "transition": args.transition,
                "transition_duration": transition_us,
            },
            {"video_url": args.video_url, "use_full_duration": True},
        ],
        "wait_export": True,
        "async_mode": False,
        "export_timeout_sec": args.export_timeout_sec,
        "api_base_url": api_base,
    }
    print("2/3 auto_render 导出中（需剪映在首页）…")
    try:
        raw = _http_auto_render(
            auto_render_url, body, timeout_sec=args.export_timeout_sec + 120
        )
    except urllib.error.HTTPError as exc:
        print(f"HTTP 错误: {exc.code} {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1

    data = _unwrap_api_data(raw)
    status = data.get("export_status")
    video_url = data.get("video_url") or ""
    if status != "completed" or not video_url:
        print(f"导出未完成: status={status!r} error={data.get('error_message')!r}", file=sys.stderr)
        return 1

    out_dir = PROJECT_ROOT / "temp" / "smoke_dissolve"
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / f"smoke_{int(time.time())}.mp4"
    print(f"   下载成片: {video_url}")
    _download_mp4(video_url, mp4_path)

    print(
        f"3/3 freezedetect 转场窗口 [{win_start:.3f}s, {win_end:.3f}s] …"
    )
    hits = _analyze_exported_mp4(str(mp4_path), win_start, win_end)
    if hits:
        for h in hits:
            print(
                f"   检测到卡顿: {h.start_sec:.3f}s ~ {h.end_sec:.3f}s "
                f"(duration {h.duration_sec:.3f}s)",
                file=sys.stderr,
            )
        print("失败: 转场前几秒存在画面冻结", file=sys.stderr)
        return 1

    print("通过: 转场检测窗口内未发现 freeze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

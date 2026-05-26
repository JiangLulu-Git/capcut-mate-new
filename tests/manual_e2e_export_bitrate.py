"""完整链路测试：API gen_video → 剪映导出（含码率）→ 轮询 → 校验 MP4。

前置：
  1. 剪映专业版已打开并在首页
  2. API 已启动且带码率环境变量（见下方「终端 1」）

终端 1 — 启动 API（含 EXPORT_BITRATE_KBPS=1000）:

  cd D:\\Skills_project\\capcut-mate
  .\\.venv\\Scripts\\Activate.ps1
  $env:EXPORT_BITRATE_KBPS = "1000"
  $env:EXPORT_BITRATE_TYPE = "VBR"
  $env:ENABLE_APIKEY = "false"
  $env:DRAFT_SAVE_PATH = "D:\\JianyingPro Drafts"
  python main.py

终端 2 — 提交导出并轮询:

  python tests/manual_e2e_export_bitrate.py 202605181452495ecf2fb7

  # 指定 API 地址（与 start-api-local.ps1 一致时用局域网 IP）
  python tests/manual_e2e_export_bitrate.py 202605181452495ecf2fb7 --api-base http://127.0.0.1:30000
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ENABLE_APIKEY", "false")


def _api_base(raw: str) -> str:
    return raw.rstrip("/")


def _post(base: str, path: str, body: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if raw.get("code") not in (None, 1):
        raise RuntimeError(json.dumps(raw, ensure_ascii=False))
    return raw.get("data") or raw


def _probe_video_bitrate_kbps(mp4_path: Path) -> float | None:
    ffprobe = os.getenv("FFPROBE_PATH", "ffprobe")
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(mp4_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return float(proc.stdout.strip()) / 1000.0
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return None


def _resolve_local_mp4(video_url: str) -> Path | None:
    if not video_url:
        return None
    marker = "/output/draft/"
    if marker in video_url:
        rel = video_url.split(marker, 1)[1].split("?", 1)[0]
        path = PROJECT_ROOT / "output" / "draft" / rel
        if path.is_file():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="gen_video 完整链路 + 码率校验")
    parser.add_argument("draft_id", help="草稿 ID（剪映首页名称一致）")
    parser.add_argument(
        "--api-base",
        default=os.getenv("E2E_API_BASE", "http://127.0.0.1:30000"),
        help="API 根地址，默认 127.0.0.1:30000",
    )
    parser.add_argument("--timeout", type=int, default=1200, help="轮询超时秒数")
    args = parser.parse_args()

    base = _api_base(args.api_base)
    api_v1 = f"{base}/openapi/capcut-mate/v1"
    draft_url = f"{api_v1}/get_draft?draft_id={args.draft_id}"

    print("=== 完整链路测试 ===")
    print(f"API:       {base}")
    print(f"draft_id:  {args.draft_id}")
    print(f"draft_url: {draft_url}")
    print("请确认：剪映在首页；API 进程已设 EXPORT_BITRATE_KBPS=1000\n")

    try:
        urllib.request.urlopen(f"{base}/openapi.json", timeout=5)
    except urllib.error.URLError as exc:
        print(f"API 未就绪 ({base}): {exc}", file=sys.stderr)
        print("请先在另一终端启动: python main.py", file=sys.stderr)
        return 1

    body = {"draft_url": draft_url}
    try:
        st0 = _post(api_v1, "/gen_video_status", body)
    except urllib.error.HTTPError as exc:
        print(f"gen_video_status HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1

    if st0.get("status") not in ("pending", "processing"):
        print("POST gen_video …")
        try:
            submit = _post(api_v1, "/gen_video", body)
            print(json.dumps(submit, ensure_ascii=False, indent=2))
        except urllib.error.HTTPError as exc:
            print(f"gen_video HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
            return 1
    else:
        print(f"已有进行中的任务: status={st0.get('status')} progress={st0.get('progress')}")

    deadline = time.time() + args.timeout
    last_key: tuple | None = None
    final: dict | None = None

    print("\n轮询 gen_video_status …")
    while time.time() < deadline:
        try:
            st = _post(api_v1, "/gen_video_status", body)
        except urllib.error.HTTPError as exc:
            print(f"  HTTP {exc.code}: {exc.read().decode()}")
            time.sleep(5)
            continue

        key = (st.get("status"), st.get("progress"))
        if key != last_key:
            print(
                f"  [{time.strftime('%H:%M:%S')}] status={st.get('status')} "
                f"progress={st.get('progress')}"
            )
            if st.get("error_message"):
                print(f"    error: {st['error_message']}")
            last_key = key

        if st.get("status") in ("completed", "failed"):
            final = st
            break
        time.sleep(5)

    if final is None:
        print(f"超时 ({args.timeout}s)", file=sys.stderr)
        return 1

    print("\n=== 最终结果 ===")
    print(json.dumps(final, ensure_ascii=False, indent=2))

    if final.get("status") != "completed":
        return 1

    video_url = final.get("video_url") or ""
    mp4 = _resolve_local_mp4(video_url)
    if mp4:
        size_kb = mp4.stat().st_size // 1024
        print(f"\n本地 MP4: {mp4} ({size_kb} KB)")
        kbps = _probe_video_bitrate_kbps(mp4)
        if kbps is not None:
            print(f"ffprobe 平均视频码率: {kbps:.0f} Kbps（目标约 1000，VBR/HEVC 会有偏差）")
    else:
        print(f"\nvideo_url: {video_url}")
        print("（非本机 output/draft 路径，跳过 ffprobe）")

    print("\n完整链路测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

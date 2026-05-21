"""本地测试：auto_render 仅建草稿、不导出（HTTP）。"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

os.environ.setdefault("ENABLE_APIKEY", "false")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.schemas.auto_render import AutoRenderRequest, VideoClipInput
from src.service.auto_render import compute_timeline_duration_us
from src.utils.video_probe import resolve_workflow_fps

API = "http://127.0.0.1:30000"
DEMO = "https://teststatic.xuesee.net/sfs/coursedesignpc/qq.mp4"


def post_json(path: str, body: dict, timeout: float = 120) -> dict:
    url = f"{API}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if raw.get("code") != 1:
        raise RuntimeError(json.dumps(raw, ensure_ascii=False))
    return raw.get("data") or {}


def main() -> int:
    urls = [DEMO, DEMO]
    fps = resolve_workflow_fps(urls)
    base = AutoRenderRequest(
        videos=[VideoClipInput(video_url=u, use_full_duration=True) for u in urls],
        default_transition="叠化",
        default_transition_duration=1_000_000,
        wait_export=False,
        async_mode=True,
        api_base_url=API,
    )
    timeline_us = compute_timeline_duration_us(base, fps)
    mid = timeline_us // 2
    print(f"成片时长: {timeline_us} us ({timeline_us / 1_000_000:.2f}s)")

    body = base.model_dump()
    body["captions"] = [
        {"text": "第一段字幕", "start": 0, "end": mid},
        {"text": "第二段字幕", "start": mid, "end": timeline_us},
    ]

    print("POST auto_render (async, wait_export=false) …")
    submit = post_json("/openapi/capcut-mate/v1/auto_render", body, timeout=30)
    task_id = submit.get("task_id") or ""
    print(f"  task_id={task_id!r} export_status={submit.get('export_status')!r}")
    if not task_id:
        print("未返回 task_id", file=sys.stderr)
        return 1

    print("轮询 auto_render_status …")
    deadline = time.time() + 600
    while time.time() < deadline:
        st = post_json(
            "/openapi/capcut-mate/v1/auto_render_status",
            {"task_id": task_id},
            timeout=120,
        )
        status = st.get("export_status")
        draft_id = st.get("draft_id") or ""
        td = st.get("timeline_duration_us")
        print(
            f"  export_status={status!r} draft_id={draft_id[:16]}… "
            f"timeline_us={td} msg={st.get('message', '')[:50]}"
        )
        if status in ("skipped", "failed", "completed"):
            print(json.dumps(st, ensure_ascii=False, indent=2))
            if status == "skipped" and draft_id:
                print("\n成功：草稿已创建，未提交导出。")
                print(f"draft_url: {st.get('draft_url')}")
                return 0
            return 1
        time.sleep(3)

    print("轮询超时", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

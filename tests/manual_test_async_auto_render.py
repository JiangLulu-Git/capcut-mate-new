"""测试 auto_render 异步模式：提交 → 轮询 auto_render_status → 直至导出完成。"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:30000"
DEMO = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)


def post_json(path: str, body: dict, timeout: float = 60) -> dict:
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
    print("1/3 POST auto_render (async_mode=true, wait_export=true) …")
    submit = post_json(
        "/openapi/capcut-mate/v1/auto_render",
        {
            "videos": [
                {
                    "video_url": DEMO,
                    "use_full_duration": True,
                    "transition": "叠化",
                    "transition_duration": 1_000_000,
                },
                {"video_url": DEMO, "use_full_duration": True},
            ],
            "wait_export": True,
            "async_mode": True,
            "api_base_url": API,
        },
        timeout=30,
    )
    task_id = submit.get("task_id") or ""
    print(f"   提交响应: export_status={submit.get('export_status')!r} task_id={task_id!r}")
    if not task_id:
        print("   错误: 未返回 task_id，请确认 API 已重启并加载 async 代码", file=sys.stderr)
        return 1

    print("2/3 轮询 auto_render_status …")
    deadline = time.time() + 1800
    last = None
    while time.time() < deadline:
        st = post_json(
            "/openapi/capcut-mate/v1/auto_render_status",
            {"task_id": task_id},
            timeout=30,
        )
        status = st.get("export_status")
        progress = st.get("progress")
        draft_id = st.get("draft_id") or ""
        msg = st.get("message") or ""
        if st != last:
            print(
                f"   [{time.strftime('%H:%M:%S')}] export_status={status!r} "
                f"progress={progress} draft_id={draft_id[:12]}… {msg[:40]}"
            )
            last = dict(st)
        if status in ("completed", "failed", "skipped"):
            print("3/3 结束")
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 0 if status == "completed" else 1
        time.sleep(5)

    print("超时", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""提交 auto_render_test.json 并轮询直至导出完成。"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = "http://172.16.94.161:30000"
BODY_PATH = Path(__file__).resolve().parents[1] / "auto_render_test.json"


def post(path: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
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
    body = json.loads(BODY_PATH.read_text(encoding="utf-8"))
    print("POST auto_render (wait_export=true) …")
    submit = post("/openapi/capcut-mate/v1/auto_render", body, timeout=60)
    task_id = submit.get("task_id") or ""
    print(json.dumps(submit, ensure_ascii=False, indent=2))
    if not task_id:
        print("无 task_id", file=sys.stderr)
        return 1

    print("\n轮询 auto_render_status …")
    deadline = time.time() + 1800
    while time.time() < deadline:
        st = post("/openapi/capcut-mate/v1/auto_render_status", {"task_id": task_id})
        status = st.get("export_status")
        print(
            f"  [{time.strftime('%H:%M:%S')}] {status!r} "
            f"progress={st.get('progress')} draft_id={(st.get('draft_id') or '')[:16]}"
        )
        if status in ("completed", "failed", "skipped"):
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 0 if status == "completed" else 1
        time.sleep(5)
    print("超时", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

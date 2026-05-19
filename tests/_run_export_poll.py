"""一次性脚本：提交 gen_video 并轮询状态（本地 API）。"""
from __future__ import annotations

import json
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("ENABLE_APIKEY", "false")
import urllib.error
import urllib.request

DRAFT_ID = sys.argv[1] if len(sys.argv) > 1 else "202605181526234a645b8c"
BASE = "http://127.0.0.1:30000/openapi/capcut-mate/v1"
DRAFT_URL = f"{BASE}/get_draft?draft_id={DRAFT_ID}"
TIMEOUT_SEC = 600


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    import config

    print(f"DRAFT_SAVE_PATH: {config.DRAFT_SAVE_PATH}")
    print(f"draft_id: {DRAFT_ID}")

    try:
        print("Submit gen_video...")
        print(post("/gen_video", {"draft_url": DRAFT_URL}))
    except urllib.error.HTTPError as exc:
        print(f"gen_video HTTP {exc.code}: {exc.read().decode()}")
        return 1

    deadline = time.time() + TIMEOUT_SEC
    last: tuple | None = None
    while time.time() < deadline:
        try:
            st = post("/gen_video_status", {"draft_url": DRAFT_URL})
        except urllib.error.HTTPError as exc:
            print(f"status HTTP {exc.code}: {exc.read().decode()}")
            time.sleep(5)
            continue

        key = (st.get("status"), st.get("progress"))
        if key != last:
            print(
                f"[{time.strftime('%H:%M:%S')}] status={st.get('status')} "
                f"progress={st.get('progress')}"
            )
            if st.get("error_message"):
                print("  error:", st["error_message"])
            if st.get("video_url"):
                print("  video_url:", st["video_url"])
            last = key

        if st.get("status") in ("completed", "failed"):
            print("FINAL:")
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 0 if st.get("status") == "completed" else 1

        time.sleep(5)

    print(f"TIMEOUT after {TIMEOUT_SEC}s")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

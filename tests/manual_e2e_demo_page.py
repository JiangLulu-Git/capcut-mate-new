"""联调演示页与协作 API（不触发剪映导出 UI）。"""
from __future__ import annotations

import json
import os
import sys
import zipfile
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("ENABLE_APIKEY", "false")

BASE = "http://127.0.0.1:30000"
V1 = f"{BASE}/openapi/capcut-mate/v1"
DEMO_VIDEO = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)


def get(url: str) -> dict:
    with urlopen(url) as r:
        return json.loads(r.read().decode())


def post_json(path: str, body: dict) -> dict:
    req = Request(
        f"{V1}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as r:
        data = json.loads(r.read().decode())
    if data.get("code") != 1:
        raise RuntimeError(data.get("message", data))
    return data.get("data") or {}


def get_api(url: str) -> dict:
    raw = get(url)
    if raw.get("code") is not None:
        if raw.get("code") != 1:
            raise RuntimeError(raw.get("message", raw))
        return raw.get("data") or {}
    return raw


def main() -> int:
    print("1. 演示页 …")
    html = urlopen(f"{BASE}/demo/").read().decode("utf-8", errors="replace")
    assert "剪映协作编辑" in html
    print("   OK /demo/")

    print("2. auto_render（不等待导出）…")
    data = post_json(
        "/auto_render",
        {
            "videos": [
                {
                    "video_url": DEMO_VIDEO,
                    "use_full_duration": True,
                    "captions": [{"text": "演示", "start": 0, "end": 3_000_000}],
                }
            ],
            "wait_export": False,
            "api_base_url": BASE,
        },
    )
    draft_id = data["draft_id"]
    print(f"   draft_id={draft_id}")

    print("3. prepare_local_edit + mate_open_url …")
    prep = get_api(f"{V1}/prepare_local_edit?{urlencode({'draft_id': draft_id})}")
    assert prep.get("mate_open_url", "").startswith("capcut-mate://")
    print(f"   mate_open_url OK")

    print("4. upload_draft 回环 …")
    import config

    draft_dir = Path(config.DRAFT_DIR) / draft_id
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        zp = tmp.name
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in draft_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(draft_dir).as_posix())
    # multipart upload
    boundary = "----test"
    body_parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="draft_id"\r\n\r\n',
        f"{draft_id}\r\n".encode(),
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="t.zip"\r\n\r\n'.encode(),
        open(zp, "rb").read(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    req = Request(
        f"{V1}/upload_draft",
        data=b"".join(body_parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(req) as r:
        up = json.loads(r.read().decode())
    os.unlink(zp)
    assert up.get("code") == 1
    print("   upload_draft OK")

    print("\n全部 API 联调通过。请在浏览器打开:")
    print(f"  {BASE}/demo/")
    print("步骤②需本机已安装剪映小助手；步骤③导出需剪映在首页。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

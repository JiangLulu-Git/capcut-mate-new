"""
本机联调：prepare_local_edit / upload_draft / 25fps 配置 /（可选）gen_video

用法（项目根目录，先另开终端启动服务: python main.py）:

  set ENABLE_APIKEY=false
  set DOWNLOAD_URL=http://127.0.0.1:30000/
  set DRAFT_URL=http://127.0.0.1:30000/openapi/capcut-mate/v1/get_draft
  python main.py

  python tests/manual_local_features_test.py
  python tests/manual_local_features_test.py --draft-id 已有草稿ID
  python tests/manual_local_features_test.py --export   # 需剪映在首页，耗时长
  python tests/manual_local_features_test.py --offline-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ENABLE_APIKEY", "false")

import config  # noqa: E402

DEFAULT_BASE = "http://127.0.0.1:30000/openapi/capcut-mate/v1"
DEMO_VIDEO = (
    "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/"
    "xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
)


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 60) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _http_multipart_upload(base: str, draft_id: str, zip_path: Path) -> dict:
    boundary = f"----capcut-mate-{int(time.time() * 1000)}"
    zip_bytes = zip_path.read_bytes()
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="draft_id"\r\n\r\n'.encode())
    parts.append(f"{draft_id}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{draft_id}.zip"\r\n'
        .encode()
    )
    parts.append(b"Content-Type: application/zip\r\n\r\n")
    parts.append(zip_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    url = f"{base.rstrip('/')}/upload_draft"
    req = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def zip_draft_dir(draft_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(draft_dir):
            for name in files:
                full = Path(root) / name
                zf.write(full, full.relative_to(draft_dir).as_posix())


def _seed_demo_video(draft_id: str, api_base: str) -> None:
    """空模板 duration=0，导出会被拒；--export 前注入一段可导出视频。"""
    from src.service.add_videos import add_videos
    from src.service.auto_render import probe_video_duration_us
    from src.service.save_draft import save_draft

    draft_url = f"{api_base.rstrip('/')}/get_draft?draft_id={draft_id}"
    print("\n=== [离线] 注入演示视频（满足 >3s 导出条件）===")
    duration_us = probe_video_duration_us(DEMO_VIDEO)
    video_infos = json.dumps(
        [
            {
                "video_url": DEMO_VIDEO,
                "start": 0,
                "end": duration_us,
                "duration": duration_us,
                "volume": 1.0,
            }
        ],
        ensure_ascii=False,
    )
    add_videos(draft_url=draft_url, video_infos=video_infos)
    save_draft(draft_url)
    print(f"  已添加视频，时长约 {duration_us / 1e6:.1f}s")


def test_offline() -> str:
    """不依赖 HTTP：创建草稿 + prepare + ingest zip + 25fps"""
    from src.service.create_draft import create_draft
    from src.service.prepare_local_edit import prepare_local_edit
    from src.service.upload_draft import ingest_uploaded_zip, _relocate_draft_path
    from src.utils import helper
    from src.utils.video_task_manager import _resolve_export_framerate
    import src.pyJianYingDraft as draft

    print("\n=== [离线] 创建草稿 ===")
    draft_url = create_draft(width=1920, height=1080)
    draft_id = helper.get_url_param(draft_url, "draft_id")
    print(f"  draft_id: {draft_id}")
    print(f"  draft_url: {draft_url}")

    print("\n=== [离线] prepare_local_edit ===")
    info = prepare_local_edit(draft_id)
    print(f"  mate_open_url: {info.get('mate_open_url', '')[:60]}…")
    print(f"  content_updated_at: {info.get('content_updated_at')}")

    assert config.EXPORT_FRAMERATE_FPS == 25
    fr = _resolve_export_framerate()
    if fr is None:
        print(
            f"\n=== [离线] 导出帧率 ===\n"
            f"  EXPORT_FRAMERATE_FPS={config.EXPORT_FRAMERATE_FPS} "
            f"(ExportFramerate 需 Windows + uiautomation，本机未加载则 gen_video 导出阶段再验证)"
        )
    else:
        assert fr.value == "25fps", fr
        print(
            f"\n=== [离线] 导出帧率 ===\n"
            f"  EXPORT_FRAMERATE_FPS={config.EXPORT_FRAMERATE_FPS} -> {fr.value}"
        )

    draft_dir = Path(config.DRAFT_DIR) / draft_id
    client_path = rf"D:\JianyingPro Drafts\{draft_id}\test.txt"
    server_path = _relocate_draft_path(client_path, draft_id, str(draft_dir))
    assert str(draft_dir) in server_path.replace("/", os.sep)
    print("\n=== [离线] 路径重写 OK ===")

    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "draft.zip"
        zip_draft_dir(draft_dir, zp)
        returned = ingest_uploaded_zip(draft_id, zp.read_bytes())
    print(f"\n=== [离线] upload_draft(ingest) OK ===\n  {returned}")
    return draft_id


def _assert_http_routes_registered() -> None:
    try:
        spec = json.loads(urlopen("http://127.0.0.1:30000/openapi.json", timeout=5).read())
    except URLError as e:
        raise SystemExit(f"无法读取 openapi.json，请先启动 python main.py: {e}") from e
    paths = spec.get("paths") or {}
    required = [
        "/openapi/capcut-mate/v1/prepare_local_edit",
        "/openapi/capcut-mate/v1/upload_draft",
    ]
    missing = [p for p in required if p not in paths]
    if missing:
        raise SystemExit(
            "端口 30000 上的服务缺少新接口 "
            f"{missing}，请先结束旧进程再启动: python main.py"
        )


def test_http(base: str, draft_id: str | None, do_export: bool) -> None:
    print(f"\n=== [HTTP] 探测服务 {base} ===")
    _assert_http_routes_registered()
    try:
        ping = _http_json("POST", f"{base}/create_draft", {"width": 1280, "height": 720})
    except URLError as e:
        print(f"  无法连接服务，请先运行: python main.py\n  错误: {e}")
        return

    if draft_id is None:
        data = ping.get("data") or ping
        draft_url = data.get("draft_url", "")
        draft_id = draft_url.split("draft_id=")[-1].split("&")[0]
        print(f"  新建草稿: {draft_id}")
    else:
        draft_url = f"{config.DRAFT_URL}?draft_id={draft_id}"
        if "draft_id=" not in draft_url:
            draft_url = f"{DEFAULT_BASE.replace('/v1', '')}/v1/get_draft?draft_id={draft_id}"
        print(f"  使用已有草稿: {draft_id}")

    q = urlencode({"draft_id": draft_id})
    prep = _http_json("GET", f"{base}/prepare_local_edit?{q}")
    prep_data = prep.get("data") or prep
    print(f"\n=== [HTTP] prepare_local_edit ===")
    print(f"  draft_url: {prep_data.get('draft_url')}")
    print(f"  mate_upload_url: {bool(prep_data.get('mate_upload_url'))}")

    draft_dir = Path(config.DRAFT_DIR) / draft_id
    if not draft_dir.is_dir():
        print(f"  跳过 upload：目录不存在 {draft_dir}")
    else:
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td) / "upload.zip"
            zip_draft_dir(draft_dir, zp)
            up = _http_multipart_upload(base, draft_id, zp)
        up_data = up.get("data") or up
        print(f"\n=== [HTTP] upload_draft ===\n  {json.dumps(up_data, ensure_ascii=False)}")

    if do_export:
        print("\n=== [HTTP] gen_video（剪映需在首页，最长等待 20 分钟）===")
        poll_url = prep_data.get("draft_url") or draft_url
        body = {"draft_url": poll_url}
        # upload_draft 可能已自动提交导出；仅在没有进行中任务时再 submit
        st0 = _http_json("POST", f"{base}/gen_video_status", body)
        sd0 = st0.get("data") or st0
        if sd0.get("status") not in ("pending", "processing"):
            gv = _http_json("POST", f"{base}/gen_video", body)
            print(f"  submit: {gv}")
        else:
            print(f"  已有导出任务，跳过重复 submit: status={sd0.get('status')}")
        deadline = time.time() + 1200
        while time.time() < deadline:
            time.sleep(5)
            st = _http_json("POST", f"{base}/gen_video_status", body)
            sd = st.get("data") or st
            status = sd.get("status")
            progress = sd.get("progress")
            print(f"  status={status} progress={progress}")
            if status in ("completed", "failed"):
                print(f"  result: {json.dumps(sd, ensure_ascii=False)}")
                break
        else:
            print("  轮询超时（1200s），请查看 main.py 日志与剪映窗口是否在首页")


def main() -> int:
    parser = argparse.ArgumentParser(description="本机功能联调")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--draft-id", default=None, help="跳过创建，用已有草稿测 HTTP")
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--export", action="store_true", help="HTTP 测试末尾提交 gen_video")
    args = parser.parse_args()

    print(f"DRAFT_SAVE_PATH={config.DRAFT_SAVE_PATH}")
    print(f"EXPORT_FRAMERATE_FPS={config.EXPORT_FRAMERATE_FPS}")

    draft_id = args.draft_id
    if not args.offline_only or draft_id is None:
        draft_id = test_offline() if draft_id is None else draft_id
        if args.export:
            _seed_demo_video(draft_id, args.base_url)
        if args.offline_only:
            print("\n全部离线检查通过。")
            return 0

    test_http(args.base_url, draft_id, args.export)
    print("\n完成。桌面端自动回传：在 desktop-client 下载草稿后改剪映并保存，观察日志 [自动同步]。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

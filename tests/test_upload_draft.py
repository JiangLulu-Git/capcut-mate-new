"""upload_draft：路径重写与 zip 入库"""

import json
import os
import zipfile
import tempfile
import shutil

import pytest

import config
from src.service.upload_draft import (
    _relocate_draft_path,
    ingest_uploaded_zip,
)


def test_relocate_draft_path_from_jianying_folder():
    draft_id = "202605181601402ca45b8f"
    server_dir = os.path.join(config.DRAFT_DIR, draft_id)
    client_path = rf"D:\JianyingPro Drafts\{draft_id}\assets\video.mp4"
    out = _relocate_draft_path(client_path, draft_id, server_dir)
    assert out == os.path.join(server_dir, "assets", "video.mp4")


def test_ingest_uploaded_zip_roundtrip(tmp_path):
    draft_id = "202605181601402ca45b8f"
    src_dir = os.path.join(config.DRAFT_DIR, draft_id)
    if not os.path.isdir(src_dir):
        pytest.skip(f"no fixture draft at {src_dir}")

    zip_path = tmp_path / "draft.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for name in files:
                full = os.path.join(root, name)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)

    backup = tempfile.mkdtemp()
    try:
        shutil.copytree(src_dir, os.path.join(backup, draft_id))
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        # 模拟用户本机路径
        patched = json.loads(
            open(os.path.join(backup, draft_id, "draft_content.json"), encoding="utf-8").read()
        )
        client_dir = rf"D:\JianyingPro Drafts\{draft_id}"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(os.path.join(backup, draft_id)):
                for name in files:
                    full = os.path.join(root, name)
                    arc = os.path.relpath(full, os.path.join(backup, draft_id))
                    if name == "draft_content.json":
                        data = json.loads(open(full, encoding="utf-8").read())
                        videos = data.get("materials", {}).get("videos", [])
                        if videos and "path" in videos[0]:
                            videos[0]["path"] = os.path.join(
                                client_dir, "assets", os.path.basename(videos[0]["path"])
                            )
                        zf.writestr(arc, json.dumps(data, ensure_ascii=False, indent=2))
                    else:
                        zf.write(full, arc)
            zip_bytes = open(zip_path, "rb").read()

        url = ingest_uploaded_zip(draft_id, zip_bytes)
        assert draft_id in url
        content_path = os.path.join(config.DRAFT_DIR, draft_id, "draft_content.json")
        assert os.path.isfile(content_path)
        with open(content_path, encoding="utf-8") as f:
            data = json.load(f)
        videos = data.get("materials", {}).get("videos", [])
        if videos and videos[0].get("path"):
            assert videos[0]["path"].startswith(os.path.join(config.DRAFT_DIR, draft_id))
    finally:
        shutil.rmtree(backup, ignore_errors=True)

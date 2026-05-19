"""用户本地剪映编辑完成后，将草稿目录 zip 回传并覆盖服务端草稿。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any, BinaryIO, Optional

import config
import src.pyJianYingDraft as draft
from exceptions import CustomException, CustomError
from src.utils.draft_cache import update_cache, DRAFT_CACHE
from src.utils.draft_downloader import copy_draft_from_project_output, patch_draft_meta_info
from src.utils.draft_lock_manager import DraftLockManager
from src.utils.logger import logger
from src.service.gen_video import gen_video


_JSON_NAMES = ("draft_content.json", "draft_info.json", "draft_meta_info.json")


def _relocate_draft_path(path: str, draft_id: str, server_draft_dir: str) -> str:
    if not isinstance(path, str) or not path.strip():
        return path
    lower = path.lower()
    if lower.startswith(("http://", "https://", "ftp://")):
        return path

    server_norm = os.path.normcase(os.path.normpath(server_draft_dir))
    if os.path.normcase(os.path.normpath(path)).startswith(server_norm):
        return path

    app_prefix = f"/app/output/draft/{draft_id}/"
    if path.startswith(app_prefix):
        rel = path[len(app_prefix) :]
        return os.path.join(server_draft_dir, rel.replace("/", os.sep))

    parts = re.split(r"[/\\]", path)
    try:
        idx = parts.index(draft_id)
    except ValueError:
        return path
    rel_parts = parts[idx + 1 :]
    if not rel_parts:
        return server_draft_dir
    return os.path.join(server_draft_dir, *rel_parts)


def _rewrite_paths_in_object(obj: Any, draft_id: str, server_draft_dir: str) -> Any:
    if isinstance(obj, dict):
        return {k: _rewrite_paths_in_object(v, draft_id, server_draft_dir) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite_paths_in_object(item, draft_id, server_draft_dir) for item in obj]
    if isinstance(obj, str):
        return _relocate_draft_path(obj, draft_id, server_draft_dir)
    return obj


def _rewrite_draft_json_files(draft_dir: str, draft_id: str) -> None:
    server_draft_dir = os.path.abspath(draft_dir)
    for name in _JSON_NAMES:
        json_path = os.path.join(draft_dir, name)
        if not os.path.isfile(json_path):
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = _rewrite_paths_in_object(data, draft_id, server_draft_dir)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("rewrote material paths in %s", json_path)


def _find_draft_root(extracted_dir: str) -> str:
    if os.path.isfile(os.path.join(extracted_dir, "draft_content.json")):
        return extracted_dir
    for name in os.listdir(extracted_dir):
        sub = os.path.join(extracted_dir, name)
        if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "draft_content.json")):
            return sub
    raise CustomException(CustomError.DRAFT_UPLOAD_INVALID)


def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            member_path = os.path.normpath(member)
            if member_path.startswith("..") or os.path.isabs(member_path):
                raise CustomException(CustomError.DRAFT_UPLOAD_INVALID)
        zf.extractall(dest_dir)


def _read_upload_with_limit(stream: BinaryIO, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise CustomException(CustomError.DRAFT_UPLOAD_TOO_LARGE)
        chunks.append(block)
    return b"".join(chunks)


def _reload_draft_cache(draft_id: str) -> None:
    content_path = os.path.join(config.DRAFT_DIR, draft_id, "draft_content.json")
    if not os.path.isfile(content_path):
        return
    script = draft.ScriptFile.load_template(content_path)
    script.save_path = content_path
    script.dual_file_compatibility = True
    update_cache(draft_id, script)


def ingest_uploaded_zip(draft_id: str, zip_bytes: bytes) -> str:
    """
    将 zip 解压到 output/draft/{draft_id}，重写素材路径并刷新内存缓存。

    Returns:
        draft_url: 与 create_draft 相同格式的 get_draft 链接
    """
    if not draft_id or len(draft_id) < 20 or len(draft_id) > 32:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    work_dir = tempfile.mkdtemp(prefix="upload_draft_", dir=config.TEMP_DIR)
    zip_path = os.path.join(work_dir, "upload.zip")
    extract_dir = os.path.join(work_dir, "extracted")

    try:
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        os.makedirs(extract_dir, exist_ok=True)
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        _safe_extract_zip(zip_path, extract_dir)
        draft_root = _find_draft_root(extract_dir)

        if os.path.exists(draft_dir):
            shutil.rmtree(draft_dir)
        shutil.copytree(draft_root, draft_dir)

        _rewrite_draft_json_files(draft_dir, draft_id)
        patch_draft_meta_info(draft_dir, draft_id)
        jianying_dir = os.path.join(config.DRAFT_SAVE_PATH, draft_id)
        if not copy_draft_from_project_output(draft_id, jianying_dir):
            logger.warning(
                "upload draft: failed to install to Jianying dir %s (gen_video may still need manual copy)",
                jianying_dir,
            )
        _reload_draft_cache(draft_id)

        draft_url = config.DRAFT_URL + "?draft_id=" + draft_id
        logger.info("upload draft success: %s -> %s", draft_id, draft_dir)
        return draft_url
    except zipfile.BadZipFile as e:
        logger.error("invalid zip for draft %s: %s", draft_id, e)
        raise CustomException(CustomError.DRAFT_UPLOAD_INVALID) from e
    except CustomException:
        raise
    except Exception as e:
        logger.error("upload draft failed for %s: %s", draft_id, e)
        raise CustomException(CustomError.DRAFT_UPLOAD_INVALID) from e
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _submit_export_after_upload(draft_url: str) -> str:
    """回传成功后由服务端提交导出任务（剪映 UI 自动化在服务端执行）。"""
    gen_video(draft_url=draft_url)
    return "processing"


async def upload_draft_async(
    draft_id: str,
    file_obj: BinaryIO,
    lock_timeout: float = 120.0,
    auto_export: Optional[bool] = None,
) -> dict:
    """
    解压入库草稿；默认在服务端自动提交 gen_video，不由客户端/Web 触发导出。
    """
    if auto_export is None:
        auto_export = config.AUTO_EXPORT_AFTER_UPLOAD

    zip_bytes = await asyncio.to_thread(
        _read_upload_with_limit, file_obj, config.UPLOAD_DRAFT_MAX_BYTES
    )

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
    except asyncio.TimeoutError:
        raise CustomException(
            CustomError.DRAFT_LOCK_TIMEOUT,
            f"Failed to acquire lock for draft {draft_id} within {lock_timeout}s",
        )

    try:
        if draft_id in DRAFT_CACHE:
            DRAFT_CACHE.pop(draft_id, None)
        draft_url = await asyncio.to_thread(ingest_uploaded_zip, draft_id, zip_bytes)
    finally:
        await lock_manager.release_lock(draft_id)

    export_status = "skipped"
    message = "草稿已回传并覆盖服务端副本"
    if auto_export:
        export_status = await asyncio.to_thread(_submit_export_after_upload, draft_url)
        message = "草稿已回传，服务端已自动提交导出任务"
        logger.info("upload_draft: auto export submitted for %s", draft_id)

    return {
        "draft_url": draft_url,
        "export_status": export_status,
        "message": message,
    }

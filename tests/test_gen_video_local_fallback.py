"""gen_video：未配置对象存储时返回本地 mp4 路径。"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import config
from src.utils.video_task_manager import VideoGenTask, VideoGenTaskManager, TaskStatus


def _make_task(outfile: str) -> VideoGenTask:
    return VideoGenTask(
        draft_url="http://127.0.0.1/get_draft?draft_id=testdraft01",
        draft_id="testdraft01",
        status=TaskStatus.PROCESSING,
        created_at=datetime.now(),
        outfile=outfile,
    )


def test_local_path_fallback_when_no_storage() -> None:
    manager = VideoGenTaskManager()
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = os.path.join(tmp, "export.mp4")
        with open(mp4, "wb") as f:
            f.write(b"\x00")

        task = _make_task(mp4)
        with (
            patch("src.utils.upload_file.is_object_storage_configured", return_value=False),
            patch.object(config, "GEN_VIDEO_LOCAL_PATH_FALLBACK", True),
            patch.object(manager, "_calculate_and_charge"),
            patch.object(manager, "_cleanup_files") as m_cleanup,
        ):
            video_url, err = manager._phase_cos_upload_finalize(task)

        assert err == ""
        assert video_url == os.path.normpath(os.path.abspath(mp4))
        m_cleanup.assert_not_called()
        assert os.path.isfile(mp4)


def test_upload_failure_when_no_storage_and_fallback_disabled() -> None:
    manager = VideoGenTaskManager()
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = os.path.join(tmp, "export.mp4")
        with open(mp4, "wb") as f:
            f.write(b"\x00")

        task = _make_task(mp4)
        with (
            patch("src.utils.upload_file.is_object_storage_configured", return_value=False),
            patch.object(config, "GEN_VIDEO_LOCAL_PATH_FALLBACK", False),
            patch.object(manager, "_calculate_and_charge"),
            patch.object(manager, "_upload_video_to_cos", return_value=("", True)),
            patch.object(manager, "_cleanup_files") as m_cleanup,
        ):
            video_url, err = manager._phase_cos_upload_finalize(task)

        assert video_url == ""
        assert err == "视频上传失败"
        m_cleanup.assert_called_once()

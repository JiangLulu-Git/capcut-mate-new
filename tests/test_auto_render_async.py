"""auto_render 异步任务：提交与状态查询。"""
from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

os.environ.setdefault("ENABLE_APIKEY", "false")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.schemas.auto_render import AutoRenderRequest, AutoRenderResponse, VideoClipInput
from src.service.auto_render import auto_render, auto_render_status
from src.utils.auto_render_task_manager import BuildPhase, auto_render_task_manager


def test_async_submit_returns_task_id() -> None:
    req = AutoRenderRequest(
        videos=[
            VideoClipInput(
                video_url="http://example.com/a.mp4",
                use_full_duration=False,
                start=0,
                end=1_000_000,
            ),
        ],
        wait_export=False,
        async_mode=True,
    )
    built = AutoRenderResponse(
        draft_id="d1",
        draft_url="http://127.0.0.1:30000/openapi/capcut-mate/v1/get_draft?draft_id=d1",
        export_status="skipped",
        message="ok",
    )
    with patch("src.service.auto_render.auto_render_build_draft", return_value=built):
        resp = auto_render(req)
    assert resp.task_id
    assert resp.export_status == "pending"
    assert resp.draft_id == ""

    deadline = time.time() + 10
    while time.time() < deadline:
        task = auto_render_task_manager.get_task(resp.task_id)
        if task and task.build_phase == BuildPhase.BUILT:
            break
        time.sleep(0.1)

    task = auto_render_task_manager.get_task(resp.task_id)
    assert task is not None
    assert task.build_phase == BuildPhase.BUILT
    assert task.draft_id == "d1"

    status = auto_render_status(resp.task_id)
    assert status.export_status == "skipped"
    assert status.draft_id == "d1"


if __name__ == "__main__":
    test_async_submit_returns_task_id()
    print("ok")

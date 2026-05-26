"""auto_render 异步任务队列：建草稿与 gen_video 导出解耦，避免 HTTP 长时间阻塞。"""
from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

import config
from exceptions import CustomException, CustomError
from src.schemas.auto_render import AutoRenderRequest, AutoRenderResponse
from src.service.gen_video import gen_video, gen_video_status
from src.utils.logger import logger

AUTO_RENDER_MAX_WORKERS = config.AUTO_RENDER_MAX_WORKERS


class BuildPhase(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    BUILT = "built"
    FAILED = "failed"


@dataclass
class AutoRenderTask:
    task_id: str
    request: AutoRenderRequest
    build_phase: BuildPhase = BuildPhase.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    draft_id: str = ""
    draft_url: str = ""
    timeline_duration_us: int = 0
    build_message: str = ""
    export_submitted: bool = False
    build_error: str = ""


class AutoRenderTaskManager:
    """auto_render 后台任务管理（单例）。"""

    _instance: Optional[AutoRenderTaskManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> AutoRenderTaskManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._tasks: Dict[str, AutoRenderTask] = {}
        self._tasks_lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []
        for i in range(AUTO_RENDER_MAX_WORKERS):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"auto_render_worker_{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        logger.info(
            "AutoRenderTaskManager started: workers=%s",
            AUTO_RENDER_MAX_WORKERS,
        )

    def submit(self, req: AutoRenderRequest) -> str:
        task_id = uuid.uuid4().hex
        task = AutoRenderTask(task_id=task_id, request=req)
        with self._tasks_lock:
            self._tasks[task_id] = task
        self._queue.put(task_id)
        logger.info(
            "auto_render task submitted: task_id=%s wait_export=%s",
            task_id,
            req.wait_export,
        )
        return task_id

    def get_task(self, task_id: str) -> Optional[AutoRenderTask]:
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def get_status_response(self, task_id: str) -> AutoRenderResponse:
        task = self.get_task(task_id)
        if task is None:
            raise CustomException(
                CustomError.VIDEO_TASK_NOT_FOUND,
                f"未找到 auto_render 任务: {task_id}",
            )

        if task.build_phase == BuildPhase.PENDING:
            return AutoRenderResponse(
                task_id=task_id,
                draft_id="",
                draft_url="",
                export_status="pending",
                progress=0,
                message="任务排队中",
            )

        if task.build_phase == BuildPhase.BUILDING:
            return AutoRenderResponse(
                task_id=task_id,
                draft_id="",
                draft_url="",
                export_status="processing",
                progress=5,
                message="正在创建草稿（下载素材、拼接时间轴）",
            )

        if task.build_phase == BuildPhase.FAILED:
            return AutoRenderResponse(
                task_id=task_id,
                draft_id=task.draft_id,
                draft_url=task.draft_url,
                export_status="failed",
                progress=0,
                timeline_duration_us=task.timeline_duration_us,
                error_message=task.build_error,
                message=f"建草稿失败: {task.build_error}",
            )

        td = task.timeline_duration_us

        # BUILT
        if not task.request.wait_export:
            return AutoRenderResponse(
                task_id=task_id,
                draft_id=task.draft_id,
                draft_url=task.draft_url,
                export_status="skipped",
                progress=100,
                timeline_duration_us=td,
                message=task.build_message or "草稿已创建，请在小助手中下载编辑；编辑完成后在 Web 点击「完成」导出",
            )

        if not task.export_submitted:
            return AutoRenderResponse(
                task_id=task_id,
                draft_id=task.draft_id,
                draft_url=task.draft_url,
                export_status="processing",
                progress=10,
                timeline_duration_us=td,
                message="草稿已创建，正在提交导出",
            )

        try:
            gv = gen_video_status(task.draft_url)
        except CustomException as exc:
            if exc.err == CustomError.VIDEO_TASK_NOT_FOUND:
                return AutoRenderResponse(
                    task_id=task_id,
                    draft_id=task.draft_id,
                    draft_url=task.draft_url,
                    export_status="processing",
                    progress=15,
                    timeline_duration_us=td,
                    message="导出任务排队中",
                )
            raise

        status = gv.get("status", "processing")
        progress = int(gv.get("progress") or 0)
        video_url = gv.get("video_url") or ""
        error_message = gv.get("error_message") or ""
        if status == "completed":
            message = "自动化成片完成"
        elif status == "failed":
            message = f"导出未完成: {error_message or status}"
        else:
            message = "正在剪映导出"

        return AutoRenderResponse(
            task_id=task_id,
            draft_id=task.draft_id,
            draft_url=task.draft_url,
            export_status=status,
            progress=progress,
            video_url=video_url,
            error_message=error_message,
            timeline_duration_us=td,
            message=message,
        )

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                task_id = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                self._run_task(task_id)
            except Exception as exc:
                logger.exception("auto_render worker error task_id=%s: %s", task_id, exc)
            finally:
                self._queue.task_done()

    def _run_task(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return

        task.build_phase = BuildPhase.BUILDING
        from src.service.auto_render import auto_render_build_draft

        try:
            built = auto_render_build_draft(task.request)
            task.draft_id = built.draft_id
            task.draft_url = built.draft_url
            task.timeline_duration_us = built.timeline_duration_us
            task.build_message = built.message or "草稿已创建"
            task.build_phase = BuildPhase.BUILT
            logger.info(
                "auto_render build done: task_id=%s draft_id=%s",
                task_id,
                task.draft_id,
            )
        except Exception as exc:
            task.build_phase = BuildPhase.FAILED
            if isinstance(exc, CustomException) and exc.detail:
                task.build_error = f"{exc.err.cn_message}({exc.detail})"
            else:
                task.build_error = str(exc)
            logger.error(
                "auto_render build failed: task_id=%s error=%s",
                task_id,
                task.build_error,
            )
            return

        if not task.request.wait_export:
            return

        try:
            gen_video(task.draft_url)
            task.export_submitted = True
            logger.info(
                "auto_render export submitted: task_id=%s draft_url=%s",
                task_id,
                task.draft_url,
            )
        except Exception as exc:
            task.build_phase = BuildPhase.FAILED
            task.build_error = f"提交导出失败: {exc}"
            logger.error(
                "auto_render gen_video submit failed: task_id=%s error=%s",
                task_id,
                exc,
            )


auto_render_task_manager = AutoRenderTaskManager()

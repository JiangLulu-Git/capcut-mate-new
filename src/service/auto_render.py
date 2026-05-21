"""

自动化成片：串联 create_draft → add_videos → add_captions → save_draft → 可选 gen_video。

本地协作编辑场景下由剪映小助手下载草稿，创建阶段不导出。

"""

from __future__ import annotations



import json

import os

import time

from typing import Any, Dict, List, Optional



import config

import src.pyJianYingDraft as draft

from exceptions import CustomException, CustomError

from src.schemas.auto_render import AutoRenderRequest, AutoRenderResponse, CaptionInput, VideoClipInput

from src.service.add_captions import add_captions

from src.service.add_videos import add_videos

from src.service.create_draft import create_draft

from src.service.gen_video import gen_video, gen_video_status

from src.service.save_draft import save_draft

from src.utils import helper

from src.utils.download import download

from src.utils.logger import logger





def _make_draft_url(draft_id: str, api_base_url: str) -> str:

    base = api_base_url.rstrip("/")

    return f"{base}/openapi/capcut-mate/v1/get_draft?draft_id={draft_id}"





def probe_video_duration_us(video_url: str, fps: int) -> int:

    """下载并探测视频全长（微秒），并按 fps 向下取整到整帧。"""

    probe_dir = os.path.join(config.TEMP_DIR, "auto_render_probe")

    os.makedirs(probe_dir, exist_ok=True)

    local_path = download(url=video_url, save_dir=probe_dir)

    duration_us = draft.VideoMaterial(local_path).duration

    if duration_us <= 0:

        raise CustomException(CustomError.INVALID_VIDEO_INFO, f"无法解析视频时长: {video_url}")

    from src.utils.video_probe import snap_duration_us_to_fps

    return snap_duration_us_to_fps(duration_us, fps)


def compute_caption_transform_y_bottom(
    canvas_height: int,
    *,
    bottom_margin_px: int = 10,
    font_size: int = 15,
) -> float:
    """
    课堂视频风格：字幕贴近底边（约 bottom_margin_px）。

    add_captions 将像素 transform_y 除以画布高度写入草稿；剪映 SRT 导入底字幕
    约为 transform_y=-0.8（负值偏下）。故：
        pixel_y = target_native * canvas_height，target_native 略大于 -0.8（留出底边距）。
    """
    if canvas_height <= 0:
        return 0.0
    line_half = max(font_size * 0.55, 8.0)
    # 相对 -0.8 底部位向上微调（native 增大 = 离底边稍远）
    lift_native = (bottom_margin_px + line_half) / canvas_height
    target_native = -0.8 + lift_native
    return target_native * canvas_height


def resolve_caption_transform_y(
    req: AutoRenderRequest,
    canvas_height: int,
) -> float:
    if req.caption_transform_y is not None:
        return float(req.caption_transform_y)
    return compute_caption_transform_y_bottom(
        canvas_height,
        bottom_margin_px=req.caption_bottom_margin_px,
        font_size=req.font_size,
    )





def _build_video_timeline_items(
    req: AutoRenderRequest, workflow_fps: int
) -> List[Dict[str, Any]]:
    """按顺序拼接时间轴条目；重叠转场时后一段提前开始。"""
    from src.utils.transition_timeline import overlap_transition_us

    items: List[Dict[str, Any]] = []
    cursor = 0
    pending_overlap_us = 0

    for index, clip in enumerate(req.videos):
        overlap_for_start = pending_overlap_us
        pending_overlap_us = 0

        if clip.use_full_duration:
            duration_us = probe_video_duration_us(clip.video_url, workflow_fps)
            start = (
                cursor - overlap_for_start
                if index > 0 and overlap_for_start > 0
                else cursor
            )
            end = start + duration_us
        else:
            if clip.start is None or clip.end is None or clip.end <= clip.start:
                raise CustomException(
                    CustomError.INVALID_VIDEO_INFO,
                    "use_full_duration=false 时必须提供有效的 start、end（微秒）",
                )
            start, end = clip.start, clip.end
            duration_us = end - start

        transition = clip.transition if clip.transition is not None else req.default_transition
        transition_duration = (
            clip.transition_duration
            if clip.transition_duration is not None
            else req.default_transition_duration
        )

        item: Dict[str, Any] = {
            "video_url": clip.video_url,
            "start": start,
            "end": end,
            "duration": duration_us,
            "volume": clip.volume,
        }
        if transition and index < len(req.videos) - 1:
            item["transition"] = transition
            item["transition_duration"] = transition_duration
            pending_overlap_us = overlap_transition_us(
                transition, transition_duration
            )

        items.append(item)
        cursor = end

    return items


def compute_timeline_duration_us(req: AutoRenderRequest, workflow_fps: int) -> int:
    """成片时间轴总时长（微秒），等于最后一段视频的 end。"""
    items = _build_video_timeline_items(req, workflow_fps)
    if not items:
        return 0
    return int(items[-1]["end"])


def _validate_captions_timeline(
    captions: List[CaptionInput],
    timeline_duration_us: int,
    workflow_fps: int,
) -> None:
    """
    校验字幕与成片时间轴一致：
    - 第一条 start 为 0
    - 最后一条 end 等于成片总时长
    - 各条字幕时长之和等于成片总时长（无空隙、无重叠）
    """
    if not captions or timeline_duration_us <= 0:
        return

    frame_us = max(1, round(1_000_000 / workflow_fps))
    tolerance = frame_us

    ordered = sorted(captions, key=lambda c: c.start)
    if ordered[0].start > tolerance:
        raise CustomException(
            CustomError.INVALID_CAPTION_INFO,
            f"第一条字幕 start 须为 0（允许 ±1 帧），当前为 {ordered[0].start} 微秒",
        )

    last_end = ordered[-1].end
    if abs(last_end - timeline_duration_us) > tolerance:
        raise CustomException(
            CustomError.INVALID_CAPTION_INFO,
            f"最后一条字幕 end（{last_end} 微秒）须等于成片时长（{timeline_duration_us} 微秒）",
        )

    total_caption_us = sum(c.end - c.start for c in ordered)
    if abs(total_caption_us - timeline_duration_us) > tolerance:
        raise CustomException(
            CustomError.INVALID_CAPTION_INFO,
            f"字幕总时长（{total_caption_us} 微秒）须等于成片时长（{timeline_duration_us} 微秒）",
        )

    for i in range(len(ordered) - 1):
        gap = ordered[i + 1].start - ordered[i].end
        if gap < -tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"字幕时间重叠：第 {i + 1} 条 end={ordered[i].end}，"
                f"第 {i + 2} 条 start={ordered[i + 1].start}",
            )
        if gap > tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"字幕存在空隙：第 {i + 1} 条 end={ordered[i].end}，"
                f"第 {i + 2} 条 start={ordered[i + 1].start}（总时长将无法对齐成片）",
            )


def _build_video_infos_json(req: AutoRenderRequest, workflow_fps: int) -> str:
    """按顺序拼接时间轴；重叠转场时后一段提前开始（与剪映手动拖拽一致）。"""
    items = _build_video_timeline_items(req, workflow_fps)
    return json.dumps(items, ensure_ascii=False)





def _build_captions_json(captions: List[CaptionInput]) -> str:

    payload = []

    for cap in captions:

        if cap.end <= cap.start:

            raise CustomException(

                CustomError.INVALID_CAPTION_INFO,

                f"字幕 end 必须大于 start: {cap.text!r}",

            )

        item: Dict[str, Any] = {

            "start": cap.start,

            "end": cap.end,

            "text": cap.text,

        }

        if cap.in_animation:

            item["in_animation"] = cap.in_animation

        if cap.out_animation:

            item["out_animation"] = cap.out_animation

        if cap.in_animation_duration is not None:

            item["in_animation_duration"] = cap.in_animation_duration

        if cap.out_animation_duration is not None:

            item["out_animation_duration"] = cap.out_animation_duration

        if cap.font_size is not None:

            item["font_size"] = cap.font_size

        payload.append(item)

    return json.dumps(payload, ensure_ascii=False)





def _wait_export(

    draft_url: str,

    timeout_sec: int,

    poll_interval_sec: float,

) -> Dict[str, Any]:

    deadline = time.time() + timeout_sec

    last_status: Optional[Dict[str, Any]] = None

    while time.time() < deadline:

        last_status = gen_video_status(draft_url)

        status = last_status.get("status")

        if status in ("completed", "failed"):

            return last_status

        time.sleep(poll_interval_sec)

    raise CustomException(

        CustomError.VIDEO_STATUS_QUERY_FAILED,

        f"等待导出超时（{timeout_sec}s）",

    )





def _install_draft_to_jianying(draft_id: str) -> bool:
    """将 output/draft 下的草稿复制到剪映草稿目录（DRAFT_SAVE_PATH）。"""
    from src.utils.draft_downloader import copy_draft_from_project_output

    target_dir = os.path.join(config.DRAFT_SAVE_PATH, draft_id)
    ok = copy_draft_from_project_output(draft_id, target_dir)
    if ok:
        logger.info(
            "auto_render: draft installed to Jianying folder draft_id=%s path=%s",
            draft_id,
            target_dir,
        )
    else:
        logger.warning(
            "auto_render: failed to install draft to Jianying folder draft_id=%s path=%s",
            draft_id,
            target_dir,
        )
    return ok





def auto_render_build_draft(req: AutoRenderRequest) -> AutoRenderResponse:
    """创建草稿 → 视频/字幕/转场 → 保存（不提交导出）。"""
    logger.info(
        "auto_render build: videos=%s captions=%s",
        len(req.videos),
        len(req.captions),
    )

    import config as app_config
    from src.utils.video_probe import (
        apply_draft_fps,
        resolve_canvas_size,
        resolve_workflow_fps,
    )

    video_urls = [v.video_url for v in req.videos]
    workflow_fps = resolve_workflow_fps(video_urls)
    use_source_canvas = req.use_source_canvas and getattr(
        app_config, "EXPORT_CANVAS_FROM_SOURCE", True
    )
    canvas_w, canvas_h = resolve_canvas_size(
        video_urls,
        width=req.width,
        height=req.height,
        use_source=use_source_canvas,
    )

    draft_url = create_draft(width=canvas_w, height=canvas_h)
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    apply_draft_fps(draft_id, workflow_fps)
    local_draft_url = _make_draft_url(draft_id, req.api_base_url)

    video_items = _build_video_timeline_items(req, workflow_fps)
    timeline_duration_us = int(video_items[-1]["end"]) if video_items else 0
    if req.captions and req.validate_caption_timeline:
        _validate_captions_timeline(req.captions, timeline_duration_us, workflow_fps)
        logger.info(
            "auto_render: captions timeline OK, count=%s timeline_us=%s",
            len(req.captions),
            timeline_duration_us,
        )

    video_infos = json.dumps(video_items, ensure_ascii=False)
    add_videos(draft_url=local_draft_url, video_infos=video_infos)
    logger.info("auto_render: videos added, draft_id=%s", draft_id)

    if req.captions:
        captions_json = _build_captions_json(req.captions)
        caption_transform_y = resolve_caption_transform_y(req, canvas_h)
        add_captions(
            draft_url=local_draft_url,
            captions=captions_json,
            text_color=req.text_color,
            font_size=req.font_size,
            alignment=1,
            transform_x=0.0,
            transform_y=caption_transform_y,
        )
        logger.info(
            "auto_render: captions added, count=%s transform_y=%s canvas_h=%s",
            len(req.captions),
            caption_transform_y,
            canvas_h,
        )

    save_draft(local_draft_url)

    jianying_installed = False
    if getattr(app_config, "AUTO_INSTALL_DRAFT_TO_JIANYING", True):
        jianying_installed = _install_draft_to_jianying(draft_id)

    if jianying_installed:
        message = (
            f"草稿已安装到剪映目录（{app_config.DRAFT_SAVE_PATH}），"
            "请在剪映首页刷新或重启剪映后打开"
        )
    else:
        message = (
            "草稿已创建（output/draft）；若剪映中未显示，"
            "请确认 DRAFT_SAVE_PATH 与剪映「草稿位置」一致，或用剪映小助手下载"
        )

    return AutoRenderResponse(
        draft_id=draft_id,
        draft_url=local_draft_url,
        export_status="skipped",
        progress=100,
        timeline_duration_us=timeline_duration_us,
        message=message,
    )


def auto_render_sync(req: AutoRenderRequest) -> AutoRenderResponse:
    """同步执行：建草稿；wait_export=true 时阻塞直到导出完成。"""
    logger.info(
        "auto_render sync: videos=%s captions=%s wait_export=%s",
        len(req.videos),
        len(req.captions),
        req.wait_export,
    )
    built = auto_render_build_draft(req)
    if not req.wait_export:
        if "剪映目录" not in built.message:
            built.message = (
                "草稿已创建，请在小助手中下载编辑；编辑完成后在 Web 点击「完成」导出"
            )
        return built

    gen_video(draft_url=built.draft_url)
    status_info = _wait_export(
        built.draft_url,
        req.export_timeout_sec,
        req.poll_interval_sec,
    )
    export_status = status_info.get("status", "failed")
    progress = int(status_info.get("progress") or 0)
    video_url = status_info.get("video_url") or ""
    error_message = status_info.get("error_message") or ""
    message = (
        "自动化成片完成"
        if export_status == "completed"
        else f"导出未完成: {error_message or export_status}"
    )
    return AutoRenderResponse(
        draft_id=built.draft_id,
        draft_url=built.draft_url,
        export_status=export_status,
        progress=progress,
        video_url=video_url,
        error_message=error_message,
        timeline_duration_us=built.timeline_duration_us,
        message=message,
    )


def auto_render(req: AutoRenderRequest) -> AutoRenderResponse:
    """
    自动化成片入口。

    - async_mode=true（默认）：立即返回 task_id，后台建草稿；wait_export 时并入 gen_video 队列。
    - async_mode=false：同步阻塞（兼容旧客户端）。
    """
    if req.async_mode:
        from src.utils.auto_render_task_manager import auto_render_task_manager

        task_id = auto_render_task_manager.submit(req)
        return AutoRenderResponse(
            task_id=task_id,
            draft_id="",
            draft_url="",
            export_status="pending",
            progress=0,
            message="任务已提交，请轮询 auto_render_status",
        )
    return auto_render_sync(req)


def auto_render_status(task_id: str) -> AutoRenderResponse:
    """查询 async_mode 提交的 auto_render 任务状态。"""
    from src.utils.auto_render_task_manager import auto_render_task_manager

    return auto_render_task_manager.get_status_response(task_id)



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

from src.schemas.auto_render import (
    AutoRenderRequest,
    AutoRenderResponse,
    CaptionInput,
    ImageClipInput,
    VideoClipInput,
)

# 画中画默认布局（videos[i] 未传 scale/transform 时使用）
DEFAULT_OVERLAY_SCALE = 0.75
DEFAULT_OVERLAY_TRANSFORM_X = -160
DEFAULT_OVERLAY_TRANSFORM_Y = 0
DEFAULT_CLIP_TRANSITION_DURATION_US = 1_000_000

from src.schemas.add_videos import SegmentInfo

from src.service.add_captions import add_captions

from src.service.add_images import add_images

from src.service.add_keyframes import add_keyframes

from src.service.add_videos import add_videos

from src.service.create_draft import create_draft

from src.service.gen_video import gen_video, gen_video_status

from src.service.save_draft import save_draft

from src.utils import helper

from src.utils.download import download
from src.utils.time_unit import TimeUnit, to_timeline_us

from src.utils.logger import logger





def _normalize_caption_input_times(cap: CaptionInput, unit: TimeUnit) -> CaptionInput:
    return cap.model_copy(
        update={
            "start": to_timeline_us(cap.start, unit),
            "end": to_timeline_us(cap.end, unit),
            "in_animation_duration": to_timeline_us(cap.in_animation_duration, unit),
            "out_animation_duration": to_timeline_us(cap.out_animation_duration, unit),
        }
    )


def normalize_auto_render_request_times(req: AutoRenderRequest) -> AutoRenderRequest:
    """将 time_unit=ms 的请求时间统一换算为内部微秒。"""
    unit: TimeUnit = req.time_unit  # type: ignore[assignment]
    if unit != "ms":
        return req

    videos = [
        v.model_copy(
            update={
                "start": to_timeline_us(v.start, unit),
                "end": to_timeline_us(v.end, unit),
                "transition_duration": to_timeline_us(v.transition_duration, unit),
                "overlay_exit_duration_us": to_timeline_us(v.overlay_exit_duration_us, unit),
                "captions": [_normalize_caption_input_times(c, unit) for c in v.captions],
            }
        )
        for v in req.videos
    ]
    images = [
        img.model_copy(
            update={
                "start": to_timeline_us(img.start, unit),
                "end": to_timeline_us(img.end, unit),
            }
        )
        for img in req.background_images
    ]
    return req.model_copy(
        update={
            "videos": videos,
            "background_images": images,
            "default_transition_duration": to_timeline_us(
                req.default_transition_duration, unit
            )
            or req.default_transition_duration,
            "time_unit": "us",
        }
    )


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
    offset_down_px: int = 0,
) -> float:
    """
    课堂视频风格：字幕贴近底边（约 bottom_margin_px）。

    add_captions 将像素 transform_y 除以画布高度写入草稿；剪映底字幕约 -0.8（半画布高单位）。
    pixel 更负 → 更靠画面下方。
    """
    if canvas_height <= 0:
        return 0.0
    line_half = max(font_size * 0.55, 8.0)
    lift_native = (bottom_margin_px + line_half) / canvas_height
    target_native = -0.8 + lift_native
    return target_native * canvas_height - float(offset_down_px)


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
        offset_down_px=req.caption_offset_down_px,
    )





def probe_image_size_px(image_url: str) -> tuple[int, int]:
    """下载并探测图片宽高（像素）。"""
    probe_dir = os.path.join(config.TEMP_DIR, "auto_render_probe")
    os.makedirs(probe_dir, exist_ok=True)
    local_path = download(url=image_url, save_dir=probe_dir)
    material = draft.VideoMaterial(local_path)
    if material.width <= 0 or material.height <= 0:
        raise CustomException(CustomError.INVALID_IMAGE_INFO, f"无法解析图片尺寸: {image_url}")
    return material.width, material.height


def _normalize_transition_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    stripped = name.strip()
    return stripped or None


def _resolve_transition_name(req: AutoRenderRequest, clip: VideoClipInput, index: int) -> Optional[str]:
    """
    转场优先级：
    1. videos[i].no_transition
    2. videos[i].transition
    3. [废弃] transitions[] / default_transition
    """
    if clip.no_transition:
        return None
    if clip.transition is not None:
        return _normalize_transition_name(clip.transition)
    if req.transitions:
        if req.transition_assign_mode == "sequential":
            slot = req.transitions[index] if index < len(req.transitions) else req.transitions[-1]
        else:
            slot = req.transitions[index % len(req.transitions)]
        return _normalize_transition_name(slot)
    return _normalize_transition_name(req.default_transition)


def _resolve_transition_duration_us(clip: VideoClipInput, req: AutoRenderRequest) -> int:
    if clip.transition_duration is not None:
        return clip.transition_duration
    return req.default_transition_duration


def _clip_needs_overlay_exit_animation(req: AutoRenderRequest, index: int) -> bool:
    """仅「当前段画中画 + 下一段全屏」时需要末尾缩放关键帧；连续两段画中画不需要。"""
    if index >= len(req.videos) - 1:
        return False
    return req.videos[index].overlay and not req.videos[index + 1].overlay


def _resolve_clip_overlay_layout(clip: VideoClipInput) -> tuple[float, float, int, int]:
    return (
        clip.scale_x if clip.scale_x is not None else DEFAULT_OVERLAY_SCALE,
        clip.scale_y if clip.scale_y is not None else DEFAULT_OVERLAY_SCALE,
        clip.transform_x if clip.transform_x is not None else DEFAULT_OVERLAY_TRANSFORM_X,
        clip.transform_y if clip.transform_y is not None else DEFAULT_OVERLAY_TRANSFORM_Y,
    )


def _build_overlay_exit_keyframes(
    req: AutoRenderRequest,
    segment_infos: List[SegmentInfo],
) -> List[Dict[str, Any]]:
    """画中画段在段末按 videos[i].overlay_exit_duration_us 关键帧过渡到全屏。"""
    keyframes: List[Dict[str, Any]] = []

    for index, seg in enumerate(segment_infos):
        if index >= len(req.videos) or not _clip_needs_overlay_exit_animation(req, index):
            continue

        clip = req.videos[index]
        anim_cfg = clip.overlay_exit_duration_us
        if anim_cfg is None or anim_cfg <= 0:
            continue

        duration_us = max(1, int(seg.end) - int(seg.start))
        anim_us = min(anim_cfg, duration_us)
        t_hold_us = duration_us - anim_us
        scale_x, scale_y, tx, ty = _resolve_clip_overlay_layout(clip)
        sid = seg.id

        for prop, hold_val, end_val in (
            ("KFTypeScaleX", scale_x, 1.0),
            ("KFTypeScaleY", scale_y, 1.0),
            ("KFTypePositionX", float(tx), 0.0),
            ("KFTypePositionY", float(ty), 0.0),
        ):
            keyframes.append(
                {
                    "segment_id": sid,
                    "property": prop,
                    "offset": t_hold_us,
                    "value": hold_val,
                }
            )
            keyframes.append(
                {
                    "segment_id": sid,
                    "property": prop,
                    "offset": duration_us,
                    "value": end_val,
                }
            )

    return keyframes


def _apply_clip_layout(item: Dict[str, Any], clip: VideoClipInput) -> None:
    if clip.overlay:
        scale_x, scale_y, tx, ty = _resolve_clip_overlay_layout(clip)
        item["scale_x"] = scale_x
        item["scale_y"] = scale_y
        item["transform_x"] = tx
        item["transform_y"] = ty
    else:
        item["scale_x"] = 1.0
        item["scale_y"] = 1.0
        item["transform_x"] = 0
        item["transform_y"] = 0


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

        transition = _resolve_transition_name(req, clip, index)
        transition_duration = _resolve_transition_duration_us(clip, req)

        item: Dict[str, Any] = {
            "video_url": clip.video_url,
            "start": start,
            "end": end,
            "duration": duration_us,
            "volume": clip.volume,
        }
        _apply_clip_layout(item, clip)
        if transition and index < len(req.videos) - 1:
            item["transition"] = transition
            item["transition_duration"] = transition_duration
            pending_overlap_us = overlap_transition_us(
                transition, transition_duration
            )

        items.append(item)
        cursor = end

    return items


def _build_background_image_items(
    images: List[ImageClipInput],
    video_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not images:
        return []

    timeline_end = int(video_items[-1]["end"]) if video_items else 0
    auto_align = (
        len(images) == len(video_items)
        and all(
            img.start is None and img.end is None and img.align_video_index is None
            for img in images
        )
    )

    payload: List[Dict[str, Any]] = []
    for index, image in enumerate(images):
        if image.align_video_index is not None:
            if image.align_video_index >= len(video_items):
                raise CustomException(
                    CustomError.INVALID_IMAGE_INFO,
                    f"background_images[{index}].align_video_index 超出视频段数",
                )
            seg = video_items[image.align_video_index]
            start, end = int(seg["start"]), int(seg["end"])
        elif auto_align:
            seg = video_items[index]
            start, end = int(seg["start"]), int(seg["end"])
        else:
            start = image.start if image.start is not None else 0
            end = image.end if image.end is not None else timeline_end

        if end <= start:
            raise CustomException(
                CustomError.INVALID_IMAGE_INFO,
                f"background_images[{index}] 时间无效: start={start}, end={end}",
            )

        width = image.width
        height = image.height
        if width is None or height is None:
            probed_w, probed_h = probe_image_size_px(image.image_url)
            width = width if width is not None else probed_w
            height = height if height is not None else probed_h

        payload.append(
            {
                "image_url": image.image_url,
                "width": int(width),
                "height": int(height),
                "start": start,
                "end": end,
            }
        )
    return payload


def compute_timeline_duration_us(req: AutoRenderRequest, workflow_fps: int) -> int:
    """成片时间轴总时长（微秒），等于最后一段视频的 end。"""
    req = normalize_auto_render_request_times(req)
    items = _build_video_timeline_items(req, workflow_fps)
    if not items:
        return 0
    return int(items[-1]["end"])


def _validate_clip_captions_relative(
    clip_index: int,
    captions: List[CaptionInput],
    segment_duration_us: int,
    workflow_fps: int,
) -> None:
    """校验 videos[i].captions：时间为相对本段起点，且不超过本段时长。"""
    if not captions or segment_duration_us <= 0:
        return

    frame_us = max(1, round(1_000_000 / workflow_fps))
    tolerance = frame_us
    ordered = sorted(captions, key=lambda c: c.start)
    for i, cap in enumerate(ordered):
        if cap.start < 0:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"videos[{clip_index}].captions[{i + 1}] start 不能小于 0",
            )
        if cap.end > segment_duration_us + tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"videos[{clip_index}].captions[{i + 1}] end（{cap.end} 微秒）"
                f"不能超过本段时长（{segment_duration_us} 微秒）",
            )
    for i in range(len(ordered) - 1):
        if ordered[i + 1].start < ordered[i].end - tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"videos[{clip_index}] 字幕重叠："
                f"第 {i + 1} 条 end={ordered[i].end}，第 {i + 2} 条 start={ordered[i + 1].start}",
            )


def _collect_timeline_captions(
    req: AutoRenderRequest,
    video_items: List[Dict[str, Any]],
) -> List[CaptionInput]:
    """将 videos[].captions（相对段首）映射到成片时间轴绝对时间。"""
    merged: List[CaptionInput] = []
    for index, clip in enumerate(req.videos):
        if index >= len(video_items) or not clip.captions:
            continue
        seg_start = int(video_items[index]["start"])
        for cap in clip.captions:
            merged.append(
                cap.model_copy(
                    update={
                        "start": seg_start + int(cap.start),
                        "end": seg_start + int(cap.end),
                    }
                )
            )
    return sorted(merged, key=lambda c: c.start)


def _validate_captions_timeline(
    captions: List[CaptionInput],
    timeline_duration_us: int,
    workflow_fps: int,
) -> None:
    """
    轻量校验字幕时间（不要求铺满整条成片）：
    - 每条 0 <= start < end <= 成片时长
    - 按 start 排序后相邻字幕不得重叠
    - 允许片头/片尾/中间无字幕（例如结尾几秒静音无字）
    """
    if not captions or timeline_duration_us <= 0:
        return

    frame_us = max(1, round(1_000_000 / workflow_fps))
    tolerance = frame_us

    ordered = sorted(captions, key=lambda c: c.start)
    for i, cap in enumerate(ordered):
        if cap.start < 0:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"第 {i + 1} 条字幕 start 不能小于 0，当前为 {cap.start} 微秒",
            )
        if cap.end > timeline_duration_us + tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"第 {i + 1} 条字幕 end（{cap.end} 微秒）不能超过成片时长"
                f"（{timeline_duration_us} 微秒）",
            )

    for i in range(len(ordered) - 1):
        if ordered[i + 1].start < ordered[i].end - tolerance:
            raise CustomException(
                CustomError.INVALID_CAPTION_INFO,
                f"字幕时间重叠：第 {i + 1} 条 end={ordered[i].end}，"
                f"第 {i + 2} 条 start={ordered[i + 1].start}",
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
    req = normalize_auto_render_request_times(req)
    logger.info(
        "auto_render build: videos=%s captions=%s",
        len(req.videos),
        sum(len(v.captions) for v in req.videos),
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
    if req.validate_caption_timeline:
        for index, clip in enumerate(req.videos):
            if index < len(video_items) and clip.captions:
                seg = video_items[index]
                _validate_clip_captions_relative(
                    index,
                    clip.captions,
                    int(seg["end"]) - int(seg["start"]),
                    workflow_fps,
                )
    all_captions = _collect_timeline_captions(req, video_items)
    if all_captions and req.validate_caption_timeline:
        _validate_captions_timeline(all_captions, timeline_duration_us, workflow_fps)
        logger.info(
            "auto_render: captions timeline OK, count=%s timeline_us=%s",
            len(all_captions),
            timeline_duration_us,
        )

    if req.background_images:
        image_items = _build_background_image_items(req.background_images, video_items)
        image_infos = json.dumps(image_items, ensure_ascii=False)
        add_images(draft_url=local_draft_url, image_infos=image_infos)
        logger.info(
            "auto_render: background images added, count=%s draft_id=%s",
            len(image_items),
            draft_id,
        )

    video_infos = json.dumps(video_items, ensure_ascii=False)
    _, _, _, _, segment_infos = add_videos(draft_url=local_draft_url, video_infos=video_infos)
    logger.info("auto_render: videos added, draft_id=%s", draft_id)

    exit_keyframes = _build_overlay_exit_keyframes(req, segment_infos)
    if exit_keyframes:
        add_keyframes(
            draft_url=local_draft_url,
            keyframes=json.dumps(exit_keyframes, ensure_ascii=False),
        )
        logger.info(
            "auto_render: overlay exit keyframes added, count=%s draft_id=%s",
            len(exit_keyframes),
            draft_id,
        )

    if all_captions:
        captions_json = _build_captions_json(all_captions)
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
            len(all_captions),
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
        sum(len(v.captions) for v in req.videos),
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



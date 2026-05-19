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





def probe_video_duration_us(video_url: str) -> int:

    """下载并探测视频全长（微秒）。"""

    probe_dir = os.path.join(config.TEMP_DIR, "auto_render_probe")

    os.makedirs(probe_dir, exist_ok=True)

    local_path = download(url=video_url, save_dir=probe_dir)

    duration_us = draft.VideoMaterial(local_path).duration

    if duration_us <= 0:

        raise CustomException(CustomError.INVALID_VIDEO_INFO, f"无法解析视频时长: {video_url}")

    return duration_us





def _build_video_infos_json(req: AutoRenderRequest) -> str:

    """按顺序拼接时间轴，支持每段全长或自定义 start/end，以及段间转场。"""

    items: List[Dict[str, Any]] = []

    cursor = 0



    for index, clip in enumerate(req.videos):

        if clip.use_full_duration:

            duration_us = probe_video_duration_us(clip.video_url)

            start, end = cursor, cursor + duration_us

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



        items.append(item)

        cursor = end



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





def auto_render(req: AutoRenderRequest) -> AutoRenderResponse:

    """

    执行完整自动化流水线。



    步骤：创建草稿 → 添加视频（含转场）→ 添加字幕 → 保存 → 可选提交导出并等待。

    本地协作编辑时设置 wait_export=false，由 Web「完成」步骤再触发 gen_video。

    """

    logger.info(

        "auto_render start: videos=%s captions=%s wait_export=%s",

        len(req.videos),

        len(req.captions),

        req.wait_export,

    )



    draft_url = create_draft(width=req.width, height=req.height)

    draft_id = helper.get_url_param(draft_url, "draft_id")

    if not draft_id:

        raise CustomException(CustomError.INVALID_DRAFT_URL)



    local_draft_url = _make_draft_url(draft_id, req.api_base_url)



    video_infos = _build_video_infos_json(req)

    add_videos(draft_url=local_draft_url, video_infos=video_infos)

    logger.info("auto_render: videos added, draft_id=%s", draft_id)



    if req.captions:

        captions_json = _build_captions_json(req.captions)

        add_captions(

            draft_url=local_draft_url,

            captions=captions_json,

            text_color=req.text_color,

            font_size=req.font_size,

        )

        logger.info("auto_render: captions added, count=%s", len(req.captions))



    save_draft(local_draft_url)



    export_status = "skipped"

    progress = 0

    video_url = ""

    error_message = ""



    if req.wait_export:

        gen_video(draft_url=local_draft_url)

        export_status = "processing"

        status_info = _wait_export(

            local_draft_url,

            req.export_timeout_sec,

            req.poll_interval_sec,

        )

        export_status = status_info.get("status", "failed")

        progress = int(status_info.get("progress") or 0)

        video_url = status_info.get("video_url") or ""

        error_message = status_info.get("error_message") or ""

        message = "自动化成片完成" if export_status == "completed" else f"导出未完成: {error_message or export_status}"

    else:

        message = "草稿已创建，请在小助手中下载编辑；编辑完成后在 Web 点击「完成」导出"



    return AutoRenderResponse(

        draft_id=draft_id,

        draft_url=local_draft_url,

        export_status=export_status,

        progress=progress,

        video_url=video_url,

        error_message=error_message,

        message=message,

    )



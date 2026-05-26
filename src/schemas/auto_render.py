"""一键自动化成片：创建草稿 → 视频/字幕/转场 → 保存 → 可选导出。"""

from __future__ import annotations



from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator





class CaptionInput(BaseModel):

    """单条字幕（时间单位见 AutoRenderRequest.time_unit，默认微秒）。"""



    text: str = Field(..., min_length=1, description="字幕文本")

    start: int = Field(
        ...,
        ge=0,
        description="开始时间（单位见 time_unit）；在 videos[].captions 中为相对本段起点 0",
    )

    end: int = Field(
        ...,
        gt=0,
        description="结束时间（单位见 time_unit）；在 videos[].captions 中不超过本段时长",
    )

    in_animation: Optional[str] = Field(default=None, description="入场动画名称")

    out_animation: Optional[str] = Field(default=None, description="出场动画名称")

    in_animation_duration: Optional[int] = Field(default=None, ge=0, description="入场动画时长（单位见 time_unit）")

    out_animation_duration: Optional[int] = Field(default=None, ge=0, description="出场动画时长（单位见 time_unit）")

    font_size: Optional[int] = Field(default=None, ge=1, description="字号")





class ImageClipInput(BaseModel):
    """背景/PPT 图片（底层轨道，先于视频添加）。"""

    image_url: str = Field(..., min_length=1, description="图片 URL")
    start: Optional[int] = Field(default=None, ge=0, description="显示开始（单位见 time_unit）；留空则自动推断")
    end: Optional[int] = Field(default=None, gt=0, description="显示结束（单位见 time_unit）；留空则自动推断")
    width: Optional[int] = Field(default=None, ge=1, description="图片宽（像素）；留空则下载后自动探测")
    height: Optional[int] = Field(default=None, ge=1, description="图片高（像素）；留空则下载后自动探测")
    align_video_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="与第 N 段视频时间轴对齐（start/end 取自该段）；优先级高于 start/end",
    )


class VideoClipInput(BaseModel):

    """单段视频素材。"""



    video_url: str = Field(..., min_length=1, description="MP4 等视频 URL")

    overlay: bool = Field(
        default=False,
        description="是否画中画小窗（叠在背景图之上）；false 为全屏",
    )

    scale_x: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description="画中画 X 缩放（overlay=true），未传默认 0.75",
    )
    scale_y: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description="画中画 Y 缩放（overlay=true），未传默认 0.75",
    )
    transform_x: Optional[int] = Field(
        default=None,
        description="画中画 X 偏移像素（overlay=true），未传默认 -160（偏左）",
    )
    transform_y: Optional[int] = Field(
        default=None,
        description="画中画 Y 偏移像素（overlay=true），未传默认 0",
    )
    overlay_exit_duration_us: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "本段画中画且下一段全屏时，段末缩放到全屏的关键帧时长（单位见 time_unit）；"
            "如 time_unit=us 时 1500000=1.5 秒，time_unit=ms 时 1500=1.5 秒；未传或 0 表示不做此动画"
        ),
    )

    no_transition: bool = Field(
        default=False,
        description="本段末尾不添加转场（硬切到下一段）",
    )
    transition: Optional[str] = Field(
        default=None,
        description="本段末尾转场名称（剪映名，如「叠化」）；传 \"\" 表示无转场；未传则无转场",
    )
    transition_duration: Optional[int] = Field(
        default=None,
        ge=0,
        description="本段末尾转场时长（单位见 time_unit）；有 transition 时未传默认 1 秒",
    )

    @model_validator(mode="before")
    @classmethod
    def _lift_legacy_per_clip_fields(cls, data: object) -> object:
        """兼容旧字段名 overlay_scale_x / overlay_transform_x 等。"""
        if not isinstance(data, dict):
            return data
        pairs = (
            ("overlay_scale_x", "scale_x"),
            ("overlay_scale_y", "scale_y"),
            ("overlay_transform_x", "transform_x"),
            ("overlay_transform_y", "transform_y"),
        )
        for old_key, new_key in pairs:
            if data.get(old_key) is not None and data.get(new_key) is None:
                data[new_key] = data[old_key]
        return data

    use_full_duration: bool = Field(

        default=True,

        description="为 true 时自动探测原视频全长并铺满时间轴片段",

    )

    start: Optional[int] = Field(default=None, ge=0, description="时间轴起始（单位见 time_unit），use_full_duration=false 时必填")

    end: Optional[int] = Field(default=None, gt=0, description="时间轴结束（单位见 time_unit），use_full_duration=false 时必填")

    volume: float = Field(default=1.0, ge=0, le=10, description="音量 0~10")

    captions: List[CaptionInput] = Field(
        default_factory=list,
        description="本段字幕；start/end 相对本段视频起点（0=段首），写入成片时自动加上段时间轴偏移",
    )





class AutoRenderRequest(BaseModel):

    """自动化成片请求。"""



    time_unit: Literal["us", "ms"] = Field(
        default="us",
        description="时间字段单位：us=微秒（默认），ms=毫秒；作用于 videos/background_images 及转场/画中画退出时长",
    )

    videos: List[VideoClipInput] = Field(..., min_length=1, description="视频列表，按顺序首尾相接")

    background_images: List[ImageClipInput] = Field(
        default_factory=list,
        description="背景/PPT 图片列表（底层）；与 videos 数量相同且未指定时间时，自动按段对齐",
    )

    use_source_canvas: bool = Field(
        default=True,
        description="画布宽高跟随第一段源视频；为 false 时使用 width/height",
    )

    width: int = Field(default=1920, ge=1, description="画布宽（use_source_canvas=false 时生效）")

    height: int = Field(default=1080, ge=1, description="画布高（use_source_canvas=false 时生效）")

    default_transition: Optional[str] = Field(
        default=None,
        description="[已废弃] 请改在 videos[i].transition 配置；仅当单段未写 transition 时作兜底",
    )

    default_transition_duration: int = Field(
        default=1_000_000,
        ge=0,
        description="[已废弃] 请改在 videos[i].transition_duration 配置；仅作兜底",
    )

    transitions: List[Optional[str]] = Field(
        default_factory=list,
        description="[已废弃] 请改在 videos[i].transition 配置",
    )

    transition_assign_mode: Literal["cycle", "sequential"] = Field(
        default="cycle",
        description="[已废弃] 配合 transitions[] 使用",
    )

    wait_export: bool = Field(

        default=False,

        description="是否在建草稿后提交 gen_video 导出；本地协作编辑可设为 false",

    )

    async_mode: bool = Field(

        default=True,

        description=(

            "true（默认）：立即返回 task_id，后台建草稿/导出，用 auto_render_status 查询；"

            "false：同步阻塞至完成（兼容旧客户端，wait_export=true 时会一直等到导出结束）"

        ),

    )

    export_timeout_sec: int = Field(default=1200, ge=60, description="等待导出超时（秒）")

    poll_interval_sec: float = Field(default=5.0, ge=1.0, description="轮询 gen_video_status 间隔（秒）")

    api_base_url: str = Field(

        default="http://127.0.0.1:30000",

        description="本服务根地址，用于拼 draft_url 供 gen_video 使用",

    )

    text_color: str = Field(default="#ffffff", description="字幕颜色")

    font_size: int = Field(default=15, ge=1, description="字幕默认字号")

    caption_bottom_margin_px: int = Field(
        default=10,
        ge=0,
        description="字幕距画布底边距（像素），越大字幕越靠上；默认 10",
    )

    caption_offset_down_px: int = Field(
        default=0,
        ge=0,
        description="在自动底部位基础上再向下偏移（像素），数值越大字幕越靠下",
    )

    caption_transform_y: Optional[float] = Field(
        default=None,
        description=(
            "字幕垂直位移（像素，剪映草稿坐标）；"
            "留空则按 caption_bottom_margin_px / caption_offset_down_px / font_size 自动计算"
        ),
    )

    validate_caption_timeline: bool = Field(
        default=False,
        description=(
            "有 captions 时做轻量校验：每条时间在 [0, 成片时长] 内且不重叠；"
            "不要求铺满全片（允许结尾几秒无字幕）。false 则完全不校验时间"
        ),
    )


class AutoRenderStatusRequest(BaseModel):

    """查询 auto_render 异步任务状态。"""

    task_id: str = Field(..., min_length=8, description="auto_render 返回的 task_id")


class AutoRenderResponse(BaseModel):
    """自动化成片业务数据（HTTP 由中间件包入 data 字段）。"""

    task_id: str = Field(
        default="",
        description="异步任务 ID（async_mode=true 时用于 auto_render_status 查询）",
    )

    draft_id: str = Field(default="", description="草稿 ID（建草稿完成后才有）")

    draft_url: str = Field(default="", description="草稿 URL（建草稿完成后才有）")

    export_status: str = Field(

        default="skipped",

        description="导出状态：skipped / processing / completed / failed",

    )

    progress: int = Field(default=0, description="导出进度 0~100")

    video_url: str = Field(default="", description="成片地址（云端 URL 或本地 mp4 路径）")

    error_message: str = Field(default="", description="失败原因")

    message: str = Field(default="", description="摘要说明")

    timeline_duration_us: int = Field(
        default=0,
        ge=0,
        description="成片时间轴总时长（微秒）；建草稿完成后有值",
    )



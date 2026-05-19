"""一键自动化成片：创建草稿 → 视频/字幕/转场 → 保存 → 可选导出。"""

from __future__ import annotations



from typing import List, Optional

from pydantic import BaseModel, Field





class CaptionInput(BaseModel):

    """单条字幕（时间单位为微秒）。"""



    text: str = Field(..., min_length=1, description="字幕文本")

    start: int = Field(..., ge=0, description="开始时间（微秒）")

    end: int = Field(..., gt=0, description="结束时间（微秒）")

    in_animation: Optional[str] = Field(default=None, description="入场动画名称")

    out_animation: Optional[str] = Field(default=None, description="出场动画名称")

    in_animation_duration: Optional[int] = Field(default=None, ge=0, description="入场动画时长（微秒）")

    out_animation_duration: Optional[int] = Field(default=None, ge=0, description="出场动画时长（微秒）")

    font_size: Optional[int] = Field(default=None, ge=1, description="字号")





class VideoClipInput(BaseModel):

    """单段视频素材。"""



    video_url: str = Field(..., min_length=1, description="MP4 等视频 URL")

    use_full_duration: bool = Field(

        default=True,

        description="为 true 时自动探测原视频全长并铺满时间轴片段",

    )

    start: Optional[int] = Field(default=None, ge=0, description="时间轴起始（微秒），use_full_duration=false 时必填")

    end: Optional[int] = Field(default=None, gt=0, description="时间轴结束（微秒），use_full_duration=false 时必填")

    transition: Optional[str] = Field(

        default=None,

        description="本段末尾转场名称（剪映规则：挂在当前段，衔接下一段）；留空则用 default_transition",

    )

    transition_duration: Optional[int] = Field(

        default=None, ge=0, description="转场时长（微秒）"

    )

    volume: float = Field(default=1.0, ge=0, le=10, description="音量 0~10")





class AutoRenderRequest(BaseModel):

    """自动化成片请求。"""



    videos: List[VideoClipInput] = Field(..., min_length=1, description="视频列表，按顺序首尾相接")

    captions: List[CaptionInput] = Field(default_factory=list, description="字幕列表，可为空")

    width: int = Field(default=1920, ge=1, description="画布宽")

    height: int = Field(default=1080, ge=1, description="画布高")

    default_transition: Optional[str] = Field(

        default="叠化",

        description="默认转场（未单独指定时使用，作用于除最后一段外的各段末尾）",

    )

    default_transition_duration: int = Field(

        default=1_000_000,

        ge=0,

        description="默认转场时长（微秒），默认 1 秒",

    )

    wait_export: bool = Field(

        default=False,

        description="是否提交 gen_video 并等待导出完成；本地协作编辑应设为 false",

    )

    export_timeout_sec: int = Field(default=1200, ge=60, description="等待导出超时（秒）")

    poll_interval_sec: float = Field(default=5.0, ge=1.0, description="轮询 gen_video_status 间隔（秒）")

    api_base_url: str = Field(

        default="http://127.0.0.1:30000",

        description="本服务根地址，用于拼 draft_url 供 gen_video 使用",

    )

    text_color: str = Field(default="#ffffff", description="字幕颜色")

    font_size: int = Field(default=15, ge=1, description="字幕默认字号")


class AutoRenderResponse(BaseModel):

    """自动化成片响应。"""



    draft_id: str = Field(..., description="草稿 ID")

    draft_url: str = Field(..., description="草稿 URL")

    export_status: str = Field(

        default="skipped",

        description="导出状态：skipped / processing / completed / failed",

    )

    progress: int = Field(default=0, description="导出进度 0~100")

    video_url: str = Field(default="", description="成片地址（云端 URL 或本地 mp4 路径）")

    error_message: str = Field(default="", description="失败原因")

    message: str = Field(default="", description="摘要说明")



from pydantic import BaseModel, Field
from typing import List, Optional


class GetTransitionsRequest(BaseModel):
    """获取转场效果列表请求参数"""
    mode: Optional[int] = Field(default=0, ge=0, le=2, description="转场模式，0=所有，1=VIP，2=免费，默认值为 0")


class TransitionItem(BaseModel):
    """转场效果信息项"""
    name: str = Field(..., description="转场名称（用于 add_videos / auto_render 的 transition 字段）")
    is_vip: bool = Field(..., description="是否为 VIP 转场")
    resource_id: str = Field(..., description="资源 ID")
    effect_id: str = Field(..., description="效果 ID")
    default_duration: int = Field(..., description="默认时长（微秒）")
    is_overlap: bool = Field(..., description="是否为重叠转场（如叠化，后段需提前开始）")


class GetTransitionsResponse(BaseModel):
    """获取转场效果列表响应参数（HTTP 由中间件包入 data 字段）"""
    transitions: List[TransitionItem] = Field(..., description="转场效果对象数组")

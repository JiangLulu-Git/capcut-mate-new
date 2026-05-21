"""公司 API 接口规范：统一 {code, message, data} 响应（见 api-standardizer 技能）。"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

API_CODE_SUCCESS = 1

T = TypeVar("T")


class ApiStandardResponse(BaseModel, Generic[T]):
    """标准 API 响应包装。"""

    code: int = Field(default=API_CODE_SUCCESS, description="1 表示成功，其它表示失败")
    message: str = Field(default="操作成功", description="接口级提示")
    data: Optional[T] = Field(default=None, description="业务数据；失败时为 null")


def is_api_success(code: Any) -> bool:
    return code == API_CODE_SUCCESS


def api_success(data: BaseModel | dict | None = None, message: str = "操作成功") -> dict:
    """构造成功响应 dict（路由层显式包装时使用；多数接口由中间件自动包装）。"""
    if isinstance(data, BaseModel):
        payload: dict | None = data.model_dump()
    elif data is None:
        payload = None
    else:
        payload = data
    return {"code": API_CODE_SUCCESS, "message": message, "data": payload}


def unwrap_api_response(body: dict) -> dict:
    """从 HTTP JSON 体解析业务 data；失败抛出 ValueError。"""
    code = body.get("code")
    if is_api_success(code):
        data = body.get("data")
        return data if isinstance(data, dict) else {}
    if code is None and "data" not in body:
        return body
    raise ValueError(
        f"API 请求失败: code={code}, message={body.get('message', '')}",
    )

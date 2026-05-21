"""测试用：解析标准 API 响应 {code, message, data}。"""
from __future__ import annotations

from typing import Any

from src.schemas.api_standard import API_CODE_SUCCESS


def unwrap_test_response(response: Any) -> dict:
    """TestClient 响应 → 业务 data 字典。"""
    body = response.json()
    code = body.get("code")
    assert code == API_CODE_SUCCESS, body
    data = body.get("data")
    return data if isinstance(data, dict) else {}

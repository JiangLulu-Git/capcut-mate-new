"""请求时间单位与内部微秒换算。"""
from __future__ import annotations

from typing import Literal, Optional

TimeUnit = Literal["us", "ms"]


def to_timeline_us(value: Optional[int], unit: TimeUnit) -> Optional[int]:
    """将请求中的时间值转为成片时间轴微秒。"""
    if value is None:
        return None
    if unit == "ms":
        return int(value) * 1000
    return int(value)


def time_field_desc(base: str, *, default_us: Optional[int] = None) -> str:
    suffix = "；单位由请求 time_unit 指定（us=微秒，ms=毫秒）"
    if default_us is not None:
        return f"{base}{suffix}；未传默认 {default_us} 微秒"
    return f"{base}{suffix}"

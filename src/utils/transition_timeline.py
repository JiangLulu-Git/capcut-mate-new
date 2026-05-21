"""转场时间轴：与剪映客户端一致的重叠放置。"""
from __future__ import annotations

from typing import Optional

import src.pyJianYingDraft as draft


def overlap_transition_us(
    transition_name: Optional[str],
    transition_duration_us: int,
) -> int:
    """重叠转场时长（微秒）；非重叠转场返回 0。"""
    if not transition_name:
        return 0
    try:
        meta = draft.TransitionType.from_name(transition_name).value
        if not meta.is_overlap:
            return 0
        if transition_duration_us > 0:
            return int(transition_duration_us)
        return meta.default_duration
    except ValueError:
        return int(transition_duration_us) if transition_duration_us > 0 else 0

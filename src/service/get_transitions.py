"""
获取转场效果列表的业务逻辑处理模块
"""
from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError


def get_transitions(mode: int = 0) -> List[Dict[str, Any]]:
    """
    获取转场效果列表

    Args:
        mode: 转场模式，0=所有，1=VIP，2=免费，默认值为 0

    Returns:
        transitions: 转场效果对象数组

    Raises:
        CustomException: 获取转场效果列表失败
    """
    logger.info(f"get_transitions called with mode: {mode}")

    try:
        if mode not in [0, 1, 2]:
            logger.error(f"Invalid mode: {mode}")
            raise CustomException(CustomError.TRANSITION_GET_FAILED)

        transitions = _get_transitions_by_mode(mode=mode)
        logger.info(f"Found {len(transitions)} transitions for mode: {mode}")
        return transitions

    except CustomException:
        logger.error(f"Get transitions failed for mode: {mode}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_transitions: {str(e)}")
        raise CustomException(CustomError.TRANSITION_GET_FAILED)


def _get_transitions_by_mode(mode: int) -> List[Dict[str, Any]]:
    from src.pyJianYingDraft.metadata.transition_meta import TransitionType

    all_transitions = []
    for transition_type in TransitionType:
        meta = transition_type.value
        all_transitions.append({
            "name": meta.name,
            "is_vip": meta.is_vip,
            "resource_id": meta.resource_id,
            "effect_id": meta.effect_id,
            "default_duration": meta.default_duration,
            "is_overlap": meta.is_overlap,
        })

    if mode == 0:
        return all_transitions
    if mode == 1:
        return [t for t in all_transitions if t["is_vip"]]
    return [t for t in all_transitions if not t["is_vip"]]

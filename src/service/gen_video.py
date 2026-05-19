from src.utils.logger import logger
from src.utils.video_task_manager import task_manager
from exceptions import CustomException, CustomError


def gen_video(draft_url: str) -> str:
    """
    提交视频生成任务（异步处理）。

    多任务可并行下载；剪映导出全局串行；上传在后台进行且不阻塞其它任务的下载与导出；
    每个 draft_url 对应独立的 VideoGenTask，保证草稿地址与成片一一对应。

    Args:
        draft_url: 草稿URL

    Returns:
        message: 响应消息
    """
    logger.info("gen_video called with draft_url: %s", draft_url)

    try:
        validate_draft_url(draft_url)
        task_manager.submit_task(draft_url)
        logger.info("Video generation task submitted for draft_url: %s", draft_url)
        return "视频生成任务已提交，请使用draft_url查询进度"

    except CustomException:
        raise
    except ValueError as e:
        logger.error("Invalid draft_url: %s, error: %s", draft_url, e)
        raise CustomException(CustomError.INVALID_DRAFT_URL) from e
    except Exception as e:
        logger.error("Submit video generation task failed: %s", e)
        raise CustomException(CustomError.INTERNAL_SERVER_ERROR) from e


def validate_draft_url(draft_url: str) -> None:
    """验证草稿URL格式是否有效"""
    if not draft_url or not isinstance(draft_url, str):
        raise ValueError("草稿URL不能为空")

    draft_id = extract_draft_id_from_url(draft_url)
    if not draft_id:
        raise ValueError("无法从URL中提取draft_id")


def extract_draft_id_from_url(draft_url: str) -> str:
    """从草稿URL中提取draft_id"""
    from src.utils import helper

    return helper.get_url_param(draft_url, "draft_id")


def gen_video_status(draft_url: str) -> dict:
    """查询视频生成任务状态"""
    logger.debug("gen_video_status called with draft_url: %s", draft_url)

    try:
        status_info = get_task_status_info(draft_url)
        logger.debug(
            "Task status retrieved for draft_url: %s, status=%s",
            draft_url,
            status_info["status"],
        )
        return status_info
    except CustomException:
        raise
    except Exception as e:
        logger.error("Get video generation status failed: %s", e)
        raise CustomException(CustomError.VIDEO_STATUS_QUERY_FAILED) from e


def get_task_status_info(draft_url: str) -> dict:
    """获取任务状态信息"""
    status_info = task_manager.get_task_status(draft_url)

    if status_info is None:
        logger.warning("No task found for draft_url: %s", draft_url)
        raise CustomException(CustomError.VIDEO_TASK_NOT_FOUND)

    return status_info


def get_gen_video_active_count() -> int:
    """返回当前排队中 + 渲染中的云渲染草稿数量（不含已完成/失败）。"""
    return task_manager.get_active_render_count()

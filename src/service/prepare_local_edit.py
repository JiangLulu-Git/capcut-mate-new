"""服务端草稿下发到用户本地剪映编辑前的元信息。"""



import os

from urllib.parse import quote



import config

from exceptions import CustomException, CustomError

from src.utils.logger import logger





def _draft_content_mtime(draft_dir: str) -> float:

    content_path = os.path.join(draft_dir, "draft_content.json")

    try:

        return os.path.getmtime(content_path)

    except OSError:

        return 0.0





def prepare_local_edit(draft_id: str) -> dict:

    """

    返回剪映小助手拉取草稿所需信息。



    典型流程：auto_render → 小助手 download 协议下载并打开剪映

    → 用户编辑 → Web「完成」upload 协议回传 → 服务端自动 gen_video → Web 轮询预览

    """

    if not draft_id:

        raise CustomException(CustomError.INVALID_DRAFT_URL)



    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)

    if not os.path.isdir(draft_dir):

        logger.info("prepare_local_edit: draft_dir not exists: %s", draft_dir)

        raise CustomException(CustomError.INVALID_DRAFT_URL)



    draft_url = config.DRAFT_URL + "?draft_id=" + draft_id

    encoded = quote(draft_url, safe="")



    return {

        "draft_id": draft_id,

        "draft_url": draft_url,

        "content_updated_at": _draft_content_mtime(draft_dir),

        "mate_open_url": f"capcut-mate://download?draft_url={encoded}&open_jianying=1",

        "mate_upload_url": f"capcut-mate://upload?draft_id={draft_id}&draft_url={encoded}",

        "mate_install_url": config.MATE_INSTALL_URL or "",

    }


def client_setup() -> dict:
    """本机协作（B 方案）首次配置说明，供演示页 / 前端拉取。"""
    install = config.MATE_INSTALL_URL or ""
    steps = [
        "在本机安装「剪映小助手」并允许 capcut-mate:// 协议（安装包需由管理员提供下载链接）。",
        "安装本机「剪映专业版」（建议 6.x），在剪映设置中将「草稿位置」记下。",
        "打开剪映小助手 → 配置中心：填写 API 地址与草稿目录（须与剪映草稿位置一致）。",
        "在本页填写相同 API 地址 → 创建任务 → 点「编辑」由小助手下载草稿并打开剪映。",
        "编辑保存后点「完成」回传；导出在云端自动完成，再点「预览」。",
    ]
    if install:
        steps[0] = f"下载并安装剪映小助手：{install}"
    return {"mate_install_url": install, "setup_steps": steps}



# 项目常量定义
import os


# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 保存剪映草稿的目录
DRAFT_DIR = os.path.join(PROJECT_ROOT, "output", "draft")

# 日志目录
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

# 临时文件目录
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

# 视频生成任务完成结果（SQLite 持久化）
VIDEO_GEN_TASK_DB_PATH = os.path.join(PROJECT_ROOT, "db", "video_gen_tasks.sqlite3")

# 视频生成任务：生成视频在 COS 上的可访问保留天数（预签名下载 URL 有效期，环境变量覆盖）
VIDEO_GEN_RETENTION_DAYS = max(1, int(os.getenv("VIDEO_GEN_RETENTION_DAYS", "7")))

# 剪映草稿的下载路径
DRAFT_URL = os.getenv("DRAFT_URL", "https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft")

# 将容器内的文件路径转成一个下载路径，执行替换操作，即将/app/ -> https://capcut-mate.jcaigc.cn/
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "https://capcut-mate.jcaigc.cn/")

# 草稿提示URL
TIP_URL = os.getenv("TIP_URL", "https://docs.jcaigc.cn/")

# 剪映小助手 Windows 安装包下载地址（演示页 / client_setup 返回，供 B 方案本机首次安装）
MATE_INSTALL_URL = os.getenv(
    "MATE_INSTALL_URL",
    "",  # 例: http://129.211.23.199:30000/static/releases/capcut-mate-windows-x64-installer.exe
)

# 贴纸配置文件路径
STICKER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "sticker.json")

# 花字配置文件路径
HUAZI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "huazi.json")

# 模板目录路径
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "template")

# 剪映草稿保存路径（安装/导出/自动导出均使用此目录，须与剪映设置中的草稿位置一致）
DRAFT_SAVE_PATH = os.getenv("DRAFT_SAVE_PATH", r"D:\JianyingPro Drafts")

# gen_video 自动导出时设置的帧率（24/25/30/50/60），对应剪映导出面板选项
EXPORT_FRAMERATE_FPS = int(os.getenv("EXPORT_FRAMERATE_FPS", "25"))

# 腾讯云对象存储配置（优先）
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_BUCKET_NAME = os.getenv("COS_BUCKET_NAME", "")
COS_REGION = os.getenv("COS_REGION", "")

# 阿里云对象存储配置（COS 未配置时作为兜底）
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "")

# API Key 计费/校验（默认关闭；仅云渲染托管场景可设 ENABLE_APIKEY=true）
ENABLE_APIKEY = os.getenv("ENABLE_APIKEY", "false").strip().lower() == "true"

# 未配置 COS/OSS 时，gen_video 导出成功后仍返回 completed，video_url 为本地 mp4 绝对路径
GEN_VIDEO_LOCAL_PATH_FALLBACK = (
    os.getenv("GEN_VIDEO_LOCAL_PATH_FALLBACK", "true").strip().lower() == "true"
)

# 文件下载大小限制（字节），默认200MB
DOWNLOAD_FILE_SIZE_LIMIT = int(os.getenv("DOWNLOAD_FILE_SIZE_LIMIT", str(200 * 1024 * 1024)))

# 用户本地编辑后回传的草稿 zip 大小上限（字节），默认 2GB
UPLOAD_DRAFT_MAX_BYTES = int(
    os.getenv("UPLOAD_DRAFT_MAX_BYTES", str(2 * 1024 * 1024 * 1024))
)

# 草稿回传成功后是否由服务端自动提交 gen_video（不由 Web/小助手触发）
AUTO_EXPORT_AFTER_UPLOAD = os.getenv("AUTO_EXPORT_AFTER_UPLOAD", "true").lower() in (
    "1",
    "true",
    "yes",
)

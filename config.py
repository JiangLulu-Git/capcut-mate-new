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

# 成片/素材对外 HTTP 根地址；gen_video 返回的 video_url 会拼成 {DOWNLOAD_URL}/output/draft/xxx.mp4
# 调用方须能访问此地址（本机调试请用局域网 IP:30000，勿用 127.0.0.1 若调用方在别的机器）
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

# 草稿时间轴 fps 与导出 fps 对齐第一段源视频探测帧率（避免 30fps 素材 + 25fps 导出错位）
EXPORT_ALIGN_SOURCE_FPS = os.getenv("EXPORT_ALIGN_SOURCE_FPS", "true").lower() in (
    "1",
    "true",
    "yes",
)

# 导出分辨率：1080P / 720P / 480P 等（剪映面板选项名，空字符串表示跟随画布/剪映默认）
EXPORT_RESOLUTION = os.getenv("EXPORT_RESOLUTION", "").strip().upper()

# auto_render 画布宽高跟随第一段源视频（不强制 1920×1080）
EXPORT_CANVAS_FROM_SOURCE = os.getenv("EXPORT_CANVAS_FROM_SOURCE", "true").lower() in (
    "1",
    "true",
    "yes",
)

# 剪映导出编码：HEVC（H.265）/ H264；空字符串表示不改剪映面板当前选项
EXPORT_CODEC = os.getenv("EXPORT_CODEC", "HEVC").strip().upper()
# 剪映导出面板里编码项的显示文案（逗号分隔，按顺序尝试点击）
EXPORT_CODEC_UI_LABELS = os.getenv(
    "EXPORT_CODEC_UI_LABELS",
    "H.265,HEVC,H265,高效,hevc",
).strip()

# 导出后处理（默认关闭，不依赖 ffmpeg）：
#   EXPORT_MP4_WEB_OPTIMIZE=false 且 EXPORT_COMPRESS_MODE=off → 直接使用剪映直出
EXPORT_MP4_WEB_OPTIMIZE = os.getenv("EXPORT_MP4_WEB_OPTIMIZE", "false").lower() in (
    "1",
    "true",
    "yes",
)

# 导出后压缩模式（需 ffmpeg；默认 off）：
#   quality / source_size / off
EXPORT_COMPRESS_MODE = os.getenv("EXPORT_COMPRESS_MODE", "off").strip().lower()

# quality 模式 CRF：18～20 几乎看不出差异，23 更小；仅 quality 模式生效
EXPORT_MP4_CRF = os.getenv("EXPORT_MP4_CRF", "20").strip()

# x264 preset：medium 同码率更清晰，slow 更慢；勿用 ultrafast 若在意画质
EXPORT_MP4_PRESET = os.getenv("EXPORT_MP4_PRESET", "medium").strip()

# 兼容旧变量：为 true 且未指定 EXPORT_COMPRESS_MODE 时等同 source_size
EXPORT_MATCH_SOURCE_SIZE = os.getenv("EXPORT_MATCH_SOURCE_SIZE", "false").lower() in (
    "1",
    "true",
    "yes",
)

# source_size：成片目标体积 ≈ 源素材 × 系数；且视频码率不低于 QUALITY_FLOOR（避免过小发糊）
EXPORT_SIZE_RATIO = max(1.0, float(os.getenv("EXPORT_SIZE_RATIO", "1.05")))
EXPORT_MATCH_QUALITY_FLOOR_BPS = int(
    os.getenv("EXPORT_MATCH_QUALITY_FLOOR_BPS", "2500000")
)
EXPORT_MATCH_MIN_VIDEO_BITRATE = int(os.getenv("EXPORT_MATCH_MIN_VIDEO_BITRATE", "400000"))
EXPORT_MATCH_MAX_VIDEO_BITRATE = int(os.getenv("EXPORT_MATCH_MAX_VIDEO_BITRATE", "12000000"))

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

# 未配置 COS/OSS 时，导出成功后 video_url 为基于 DOWNLOAD_URL 的可下载 HTTP 地址
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

# 建草稿完成后复制到剪映草稿目录，否则只存在于 output/draft，剪映首页看不到
AUTO_INSTALL_DRAFT_TO_JIANYING = os.getenv(
    "AUTO_INSTALL_DRAFT_TO_JIANYING", "true"
).strip().lower() in ("1", "true", "yes")

# auto_render 字幕默认距画布底边（像素），课堂视频风格
CAPTION_BOTTOM_MARGIN_PX = max(0, int(os.getenv("CAPTION_BOTTOM_MARGIN_PX", "10")))

# auto_render 异步建草稿并发（下载素材 + 写草稿）；剪映导出仍由 gen_video 全局串行
AUTO_RENDER_MAX_WORKERS = max(
    1,
    min(5, int(os.getenv("AUTO_RENDER_MAX_WORKERS", "5"))),
)

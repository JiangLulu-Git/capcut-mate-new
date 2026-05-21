"""将项目内文件路径转为调用方可 HTTP 下载的 URL（依赖 config.DOWNLOAD_URL）。"""
import os

import config


def to_public_download_url(path_or_url: str) -> str:
    """
    已是 http(s) 则原样返回；否则按 PROJECT_ROOT 相对路径拼 DOWNLOAD_URL。
  调用方须能访问 DOWNLOAD_URL 对应主机（本机调试请用局域网 IP，勿用 127.0.0.1）。
    """
    if not path_or_url or not str(path_or_url).strip():
        return ""
    value = str(path_or_url).strip()
    lower = value.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return value
    file_path = os.path.normpath(os.path.abspath(value))
    try:
        relative_path = os.path.relpath(file_path, config.PROJECT_ROOT)
    except ValueError:
        relative_path = file_path
    relative_path = relative_path.replace(os.sep, "/")
    base_url = config.DOWNLOAD_URL.rstrip("/")
    return f"{base_url}/{relative_path}"

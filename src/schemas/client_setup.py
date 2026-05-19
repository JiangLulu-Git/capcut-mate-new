from pydantic import BaseModel, Field


class ClientSetupResponse(BaseModel):
    mate_install_url: str = Field(
        default="",
        description="剪映小助手安装包下载地址（未配置时为空，由演示页提示手动安装）",
    )
    setup_steps: list[str] = Field(
        default_factory=list,
        description="本机首次使用步骤说明",
    )

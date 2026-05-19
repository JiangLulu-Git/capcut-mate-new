from pydantic import BaseModel, Field


class UploadDraftResponse(BaseModel):
    """上传本地编辑后的草稿包"""

    draft_url: str = Field(..., description="草稿 URL，与 create_draft 返回格式一致")
    export_status: str = Field(
        default="skipped",
        description="导出状态：skipped（未提交）/ processing（已提交任务）",
    )
    message: str = Field(default="草稿已回传并覆盖服务端副本", description="提示信息")

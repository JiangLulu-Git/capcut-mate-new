from pydantic import BaseModel, Field





class PrepareLocalEditRequest(BaseModel):

    draft_id: str = Field(..., min_length=20, max_length=32, description="草稿 ID")





class PrepareLocalEditResponse(BaseModel):

    draft_id: str = Field(..., description="草稿 ID")

    draft_url: str = Field(..., description="get_draft 链接，供客户端解析 draft_id")

    content_updated_at: float = Field(

        default=0.0,

        description="draft_content.json 最后修改时间（Unix 秒），用于判断回传是否完成",

    )

    mate_open_url: str = Field(

        default="",

        description="唤起小助手下载草稿并打开剪映",

    )

    mate_upload_url: str = Field(

        default="",

        description="唤起小助手打包本机草稿并回传服务器",

    )

    mate_install_url: str = Field(

        default="",

        description="剪映小助手安装包下载地址",

    )



from typing import Optional
from pydantic import BaseModel, Field


class UploadFileOutSchema(BaseModel):
    """Composer 附件上传结果"""
    url: str
    original_name: str
    size: int
    mime_type: Optional[str] = None
    hash: Optional[str] = None
    is_image: bool = False


class MarkdownPreviewInSchema(BaseModel):
    """Markdown 预览请求"""
    content: str = Field("", description="Markdown 原文")


class MarkdownPreviewOutSchema(BaseModel):
    """Markdown 预览结果"""
    html: str

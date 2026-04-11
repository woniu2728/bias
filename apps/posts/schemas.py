"""
帖子系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class PostCreateSchema(BaseModel):
    """创建帖子（回复讨论）"""
    content: str = Field(..., min_length=1, description="帖子内容")

    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('内容不能为空')
        return v.strip()


class PostUpdateSchema(BaseModel):
    """更新帖子"""
    content: str = Field(..., min_length=1, description="帖子内容")

    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('内容不能为空')
        return v.strip()


class PostReportSchema(BaseModel):
    """举报帖子"""
    reason: str = Field(..., min_length=1, max_length=100, description="举报原因")
    message: str = Field("", max_length=1000, description="补充说明")

    @validator('reason')
    def validate_reason(cls, v):
        if not v.strip():
            raise ValueError('举报原因不能为空')
        return v.strip()

    @validator('message')
    def validate_message(cls, v):
        return (v or "").strip()


class PostFilterSchema(BaseModel):
    """帖子列表过滤"""
    author: Optional[str] = Field(None, description="作者用户名")
    user_id: Optional[int] = Field(None, description="作者用户ID")
    page: int = Field(1, ge=1, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class UserSimpleSchema(BaseModel):
    """简化的用户信息"""
    id: int
    username: str
    display_name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class PostOutSchema(BaseModel):
    """帖子输出"""
    id: int
    discussion_id: int
    number: int
    user: Optional[UserSimpleSchema] = None
    type: str
    content: str
    content_html: str
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    edited_user: Optional[UserSimpleSchema] = None
    discussion: Optional[dict] = None
    is_hidden: bool
    like_count: int = 0
    is_liked: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_like: bool = False

    class Config:
        from_attributes = True


class PostListSchema(BaseModel):
    """帖子列表输出"""
    total: int
    page: int
    limit: int
    data: List[PostOutSchema]

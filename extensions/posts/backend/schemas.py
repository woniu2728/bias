"""
帖子系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class PostCreateSchema(BaseModel):
    """创建帖子（回复讨论）"""
    content: str = Field(..., min_length=1, description="帖子内容")
    reply_to_post_id: Optional[int] = Field(None, ge=1, description="被回复的帖子ID")

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


class UserSimpleSchema(BaseModel):
    """简化的用户信息"""
    class GroupBadgeSchema(BaseModel):
        id: int
        name: str
        color: str = ""
        icon: str = ""
        is_hidden: bool = False

        class Config:
            from_attributes = True

    id: int
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    primary_group: Optional[GroupBadgeSchema] = None

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
    approval_status: str = "approved"
    approval_note: str = ""
    can_edit: bool = False
    can_delete: bool = False
    post_type: Optional[dict] = None
    event_data: Optional[dict] = None

    class Config:
        from_attributes = True

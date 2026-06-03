"""
帖子系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List
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


class PostFilterSchema(BaseModel):
    """帖子列表过滤"""
    author: Optional[str] = Field(None, description="作者用户名")
    user_id: Optional[int] = Field(None, description="作者用户ID")
    page: int = Field(1, ge=1, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


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
    like_count: int = 0
    is_liked: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_like: bool = False
    can_flag: bool = False
    post_type: Optional[dict] = None
    event_data: Optional[dict] = None
    viewer_has_open_flag: bool = False
    open_flag_count: int = 0
    open_flags: List[dict] = []
    flags: List[dict] = []
    can_moderate_flags: bool = False

    class Config:
        from_attributes = True


class PostListSchema(BaseModel):
    """帖子列表输出"""
    total: int
    page: int
    limit: int
    current_start: int = 1
    current_end: int = 1
    has_previous: bool = False
    has_more: bool = False
    data: List[PostOutSchema]

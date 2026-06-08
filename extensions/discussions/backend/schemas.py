"""
讨论系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class DiscussionCreateSchema(BaseModel):
    """创建讨论"""
    title: str = Field(..., min_length=1, max_length=200, description="讨论标题")
    content: str = Field(..., min_length=1, description="第一条帖子内容")

    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()


class DiscussionUpdateSchema(BaseModel):
    """更新讨论"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="讨论标题")
    content: Optional[str] = Field(None, min_length=1, description="第一条帖子内容")
    is_locked: Optional[bool] = Field(None, description="是否锁定")
    is_sticky: Optional[bool] = Field(None, description="是否置顶")
    is_hidden: Optional[bool] = Field(None, description="是否隐藏")

    @validator('title')
    def validate_optional_title(cls, v):
        if v is None:
            return v
        if not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()


class DiscussionReadStateSchema(BaseModel):
    """讨论阅读状态更新"""
    last_read_post_number: int = Field(..., ge=1, description="最后已读楼层")


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

class DiscussionOutSchema(BaseModel):
    """讨论输出"""
    id: int
    title: str
    slug: str
    user: Optional[UserSimpleSchema] = None
    created_at: datetime
    updated_at: datetime
    last_posted_at: Optional[datetime] = None
    last_posted_user: Optional[UserSimpleSchema] = None
    last_post_number: Optional[int] = None
    comment_count: int
    participant_count: int
    view_count: int
    is_locked: bool
    is_sticky: bool
    is_hidden: bool
    approval_status: str = "approved"
    approval_note: str = ""
    is_subscribed: bool = False
    is_unread: bool = False
    unread_count: int = 0
    last_read_at: Optional[datetime] = None
    last_read_post_number: int = 0
    hidden_at: Optional[datetime] = None
    tags: List[dict] = []

    class Config:
        from_attributes = True

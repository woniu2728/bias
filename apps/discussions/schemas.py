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
    tag_ids: Optional[List[int]] = Field(default=[], description="标签ID列表")

    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()


class DiscussionUpdateSchema(BaseModel):
    """更新讨论"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="讨论标题")
    is_locked: Optional[bool] = Field(None, description="是否锁定")
    is_sticky: Optional[bool] = Field(None, description="是否置顶")
    is_hidden: Optional[bool] = Field(None, description="是否隐藏")


class DiscussionReadStateSchema(BaseModel):
    """讨论阅读状态更新"""
    last_read_post_number: int = Field(..., ge=1, description="最后已读楼层")


class DiscussionFilterSchema(BaseModel):
    """讨论列表过滤"""
    q: Optional[str] = Field(None, description="搜索关键词")
    tag: Optional[str] = Field(None, description="标签slug")
    author: Optional[str] = Field(None, description="作者用户名")
    subscription: Optional[str] = Field(None, description="订阅过滤: following")
    sort: Optional[str] = Field('latest', description="排序方式: latest, top, oldest, newest")
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


class DiscussionListSchema(BaseModel):
    """讨论列表输出"""
    total: int
    page: int
    limit: int
    data: List[DiscussionOutSchema]


class DiscussionDetailSchema(DiscussionOutSchema):
    """讨论详情输出（包含第一条帖子）"""
    first_post: Optional[dict] = None
    can_edit: bool = False
    can_delete: bool = False
    can_reply: bool = False

    class Config:
        from_attributes = True

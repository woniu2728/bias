"""
通知系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class NotificationFilterSchema(BaseModel):
    """通知列表过滤"""
    is_read: Optional[bool] = Field(None, description="是否已读（不传表示全部）")
    type: Optional[str] = Field(None, description="通知类型")
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


class NotificationOutSchema(BaseModel):
    """通知输出"""
    id: int
    user_id: int
    from_user: Optional[UserSimpleSchema] = None
    type: str
    subject_type: Optional[str] = None
    subject_id: Optional[int] = None
    data: dict
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListSchema(BaseModel):
    """通知列表输出"""
    total: int
    unread_count: int
    page: int
    limit: int
    type_counts: Dict[str, int] = {}
    unread_type_counts: Dict[str, int] = {}
    data: List[NotificationOutSchema]


class NotificationStatsSchema(BaseModel):
    """通知统计"""
    total: int
    unread_count: int
    read_count: int

"""
Pydantic schemas for User API
"""
from ninja import Schema
from datetime import datetime
from typing import Optional, List


class UserRegisterSchema(Schema):
    """用户注册Schema"""
    username: str
    email: str
    password: str
    human_verification_token: Optional[str] = None


class UserLoginSchema(Schema):
    """用户登录Schema"""
    identification: str  # 用户名或邮箱
    password: str
    human_verification_token: Optional[str] = None


class TokenSchema(Schema):
    """Token响应Schema"""
    access: str
    refresh: str


class UserOutSchema(Schema):
    """用户输出Schema"""
    class GroupBadgeSchema(Schema):
        id: int
        name: str
        color: str = ""
        icon: str = ""
        is_hidden: bool = False

    id: int
    username: str
    display_name: str
    email: str
    avatar_url: Optional[str] = None
    bio: str = ""
    is_email_confirmed: bool
    joined_at: datetime
    last_seen_at: datetime
    discussion_count: int
    comment_count: int
    is_suspended: bool
    is_staff: bool = False
    primary_group: Optional[GroupBadgeSchema] = None

    class Config:
        from_attributes = True


class UserUpdateSchema(Schema):
    """用户更新Schema"""
    display_name: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[str] = None


class PasswordChangeSchema(Schema):
    """修改密码Schema"""
    old_password: str
    new_password: str


class PasswordResetRequestSchema(Schema):
    """请求重置密码Schema"""
    email: str


class PasswordResetSchema(Schema):
    """重置密码Schema"""
    token: str
    password: str


class EmailVerifySchema(Schema):
    """邮箱验证Schema"""
    token: str


class GroupOutSchema(Schema):
    """用户组输出Schema"""
    id: int
    name: str
    name_singular: str
    name_plural: str
    color: str
    icon: str
    is_hidden: bool

    class Config:
        from_attributes = True


class UserDetailSchema(UserOutSchema):
    """用户详情Schema（包含用户组）"""
    groups: List[GroupOutSchema] = []
    preferences: dict = {}


class CurrentUserSchema(UserDetailSchema):
    """当前用户详情Schema（包含封禁信息）"""
    suspended_until: Optional[datetime] = None
    suspend_reason: str = ""
    suspend_message: str = ""
    forum_permissions: List[str] = []


class UserPreferencesSchema(Schema):
    """用户偏好Schema"""
    follow_after_reply: bool = False
    follow_after_create: bool = False
    notify_new_post: bool = True

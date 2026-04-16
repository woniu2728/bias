"""
标签系统的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class TagCreateSchema(BaseModel):
    """创建标签"""
    name: str = Field(..., min_length=1, max_length=100, description="标签名称")
    slug: Optional[str] = Field(None, max_length=100, description="标签slug（可选，自动生成）")
    description: Optional[str] = Field("", description="标签描述")
    color: Optional[str] = Field("", max_length=20, description="标签颜色")
    icon: Optional[str] = Field("", max_length=100, description="标签图标")
    background_url: Optional[str] = Field("", description="背景图片URL")
    position: Optional[int] = Field(0, description="排序位置")
    parent_id: Optional[int] = Field(None, description="父标签ID")
    is_hidden: Optional[bool] = Field(False, description="是否隐藏")
    is_restricted: Optional[bool] = Field(False, description="是否限制发帖")
    view_scope: Optional[str] = Field("public", description="查看权限级别")
    start_discussion_scope: Optional[str] = Field("members", description="发帖权限级别")
    reply_scope: Optional[str] = Field("members", description="回帖权限级别")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('标签名称不能为空')
        return v.strip()


class TagUpdateSchema(BaseModel):
    """更新标签"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="标签名称")
    slug: Optional[str] = Field(None, max_length=100, description="标签slug")
    description: Optional[str] = Field(None, description="标签描述")
    color: Optional[str] = Field(None, max_length=20, description="标签颜色")
    icon: Optional[str] = Field(None, max_length=100, description="标签图标")
    background_url: Optional[str] = Field(None, description="背景图片URL")
    position: Optional[int] = Field(None, description="排序位置")
    parent_id: Optional[int] = Field(None, description="父标签ID")
    is_hidden: Optional[bool] = Field(None, description="是否隐藏")
    is_restricted: Optional[bool] = Field(None, description="是否限制发帖")
    view_scope: Optional[str] = Field(None, description="查看权限级别")
    start_discussion_scope: Optional[str] = Field(None, description="发帖权限级别")
    reply_scope: Optional[str] = Field(None, description="回帖权限级别")


class TagFilterSchema(BaseModel):
    """标签列表过滤"""
    parent_id: Optional[int] = Field(None, description="父标签ID（null表示顶级标签）")
    include_hidden: bool = Field(False, description="是否包含隐藏标签")


class TagOutSchema(BaseModel):
    """标签输出"""
    id: int
    name: str
    slug: str
    description: str
    color: str
    icon: str
    background_url: str
    position: int
    parent_id: Optional[int] = None
    is_hidden: bool
    is_restricted: bool
    view_scope: str = "public"
    start_discussion_scope: str = "members"
    reply_scope: str = "members"
    can_start_discussion: bool = False
    can_reply: bool = False
    discussion_count: int
    last_posted_at: Optional[datetime] = None
    last_posted_discussion: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    children: List['TagOutSchema'] = []

    class Config:
        from_attributes = True


class TagSimpleSchema(BaseModel):
    """简化的标签信息"""
    id: int
    name: str
    slug: str
    color: str
    icon: str

    class Config:
        from_attributes = True


class TagListSchema(BaseModel):
    """标签列表输出"""
    data: List[TagOutSchema]


# 解决循环引用
TagOutSchema.model_rebuild()

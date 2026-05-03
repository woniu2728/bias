"""
搜索功能的Pydantic Schema定义
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class SearchQuerySchema(BaseModel):
    """搜索查询"""
    q: str = Field(..., min_length=1, description="搜索关键词")
    type: Optional[Literal['all', 'discussions', 'posts', 'users']] = Field(
        'all',
        description="搜索类型: all, discussions, posts, users"
    )
    page: int = Field(1, ge=1, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class UserSearchResultSchema(BaseModel):
    """用户搜索结果"""
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
    bio: str
    discussion_count: int
    comment_count: int
    joined_at: datetime
    primary_group: Optional[GroupBadgeSchema] = None

    class Config:
        from_attributes = True


class DiscussionSearchResultSchema(BaseModel):
    """讨论搜索结果"""
    id: int
    title: str
    slug: str
    user: Optional[dict] = None
    comment_count: int
    view_count: int
    is_sticky: bool
    is_locked: bool
    created_at: datetime
    last_posted_at: Optional[datetime] = None
    excerpt: Optional[str] = None  # 摘要

    class Config:
        from_attributes = True


class PostSearchResultSchema(BaseModel):
    """帖子搜索结果"""
    id: int
    discussion_id: int
    discussion_title: str
    number: int
    user: Optional[dict] = None
    content: str
    created_at: datetime
    excerpt: Optional[str] = None  # 摘要

    class Config:
        from_attributes = True


class SearchResultSchema(BaseModel):
    """搜索结果"""
    total: int
    page: int
    limit: int
    type: str
    discussion_total: int = 0
    post_total: int = 0
    user_total: int = 0
    discussions: List[DiscussionSearchResultSchema] = []
    posts: List[PostSearchResultSchema] = []
    users: List[UserSearchResultSchema] = []


class SearchSuggestionSchema(BaseModel):
    """搜索建议"""
    suggestions: List[str]


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

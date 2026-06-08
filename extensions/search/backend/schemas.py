from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UserSearchResultSchema(BaseModel):
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
    excerpt: Optional[str] = None

    class Config:
        from_attributes = True


class PostSearchResultSchema(BaseModel):
    id: int
    discussion_id: int
    discussion_title: str
    number: int
    user: Optional[dict] = None
    content: str
    created_at: datetime
    excerpt: Optional[str] = None

    class Config:
        from_attributes = True


class SearchResultSchema(BaseModel):
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
    suggestions: List[str]


class SearchFilterDefinitionSchema(BaseModel):
    code: str
    label: str
    module_id: str
    target: str
    syntax: str = ""
    description: str = ""


class SearchFilterCatalogSchema(BaseModel):
    target: str = "all"
    filters: List[SearchFilterDefinitionSchema] = []

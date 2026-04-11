"""
标签系统业务逻辑层
"""
from datetime import datetime
from typing import Optional, List
from django.db import transaction
from django.db.models import Q, F, Count
from django.core.exceptions import PermissionDenied
from apps.tags.models import Tag, DiscussionTag
from apps.users.models import User


class TagService:
    """标签服务"""

    @staticmethod
    def create_tag(
        name: str,
        slug: Optional[str] = None,
        description: str = "",
        color: str = "",
        icon: str = "",
        background_url: str = "",
        position: int = 0,
        parent_id: Optional[int] = None,
        is_hidden: bool = False,
        is_restricted: bool = False,
        user: Optional[User] = None,
    ) -> Tag:
        """
        创建标签

        Args:
            name: 标签名称
            slug: 标签slug（可选）
            description: 描述
            color: 颜色
            icon: 图标
            background_url: 背景图片
            position: 排序位置
            parent_id: 父标签ID
            is_hidden: 是否隐藏
            is_restricted: 是否限制发帖
            user: 操作用户

        Returns:
            Tag: 创建的标签对象

        Raises:
            PermissionDenied: 权限不足
            ValueError: 参数错误
        """
        # 权限检查
        if user and not user.is_staff:
            raise PermissionDenied("只有管理员可以创建标签")

        # 检查父标签
        parent = None
        if parent_id:
            try:
                parent = Tag.objects.get(id=parent_id)
            except Tag.DoesNotExist:
                raise ValueError("父标签不存在")

        with transaction.atomic():
            tag = Tag.objects.create(
                name=name,
                slug=slug or "",  # 如果为空，save方法会自动生成
                description=description,
                color=color,
                icon=icon,
                background_url=background_url,
                position=position,
                parent=parent,
                is_hidden=is_hidden,
                is_restricted=is_restricted,
            )

            return tag

    @staticmethod
    def get_tag_list(
        parent_id: Optional[int] = None,
        include_hidden: bool = False,
    ) -> List[Tag]:
        """
        获取标签列表

        Args:
            parent_id: 父标签ID（None表示顶级标签）
            include_hidden: 是否包含隐藏标签

        Returns:
            List[Tag]: 标签列表
        """
        queryset = Tag.objects.all()

        # 过滤父标签
        if parent_id is None:
            queryset = queryset.filter(parent__isnull=True)
        else:
            queryset = queryset.filter(parent_id=parent_id)

        # 过滤隐藏标签
        if not include_hidden:
            queryset = queryset.filter(is_hidden=False)

        # 排序
        queryset = queryset.order_by('position', 'name')

        tags = list(queryset)

        # 递归加载子标签（使用临时属性）
        for tag in tags:
            tag._children_list = TagService._get_children(tag.id, include_hidden)

        return tags

    @staticmethod
    def _get_children(parent_id: int, include_hidden: bool = False) -> List[Tag]:
        """
        递归获取子标签

        Args:
            parent_id: 父标签ID
            include_hidden: 是否包含隐藏标签

        Returns:
            List[Tag]: 子标签列表
        """
        queryset = Tag.objects.filter(parent_id=parent_id)

        if not include_hidden:
            queryset = queryset.filter(is_hidden=False)

        queryset = queryset.order_by('position', 'name')
        children = list(queryset)

        # 递归加载子标签的子标签（使用临时属性）
        for child in children:
            child._children_list = TagService._get_children(child.id, include_hidden)

        return children

    @staticmethod
    def get_tag_by_id(tag_id: int) -> Optional[Tag]:
        """
        获取标签详情

        Args:
            tag_id: 标签ID

        Returns:
            Optional[Tag]: 标签对象
        """
        try:
            tag = Tag.objects.get(id=tag_id)
            # 加载子标签
            tag.children = TagService._get_children(tag.id, include_hidden=True)
            return tag
        except Tag.DoesNotExist:
            return None

    @staticmethod
    def get_tag_by_slug(slug: str) -> Optional[Tag]:
        """
        通过slug获取标签

        Args:
            slug: 标签slug

        Returns:
            Optional[Tag]: 标签对象
        """
        try:
            tag = Tag.objects.get(slug=slug)
            # 加载子标签
            tag.children = TagService._get_children(tag.id, include_hidden=True)
            return tag
        except Tag.DoesNotExist:
            return None

    @staticmethod
    def update_tag(
        tag_id: int,
        user: User,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        background_url: Optional[str] = None,
        position: Optional[int] = None,
        parent_id: Optional[int] = None,
        is_hidden: Optional[bool] = None,
        is_restricted: Optional[bool] = None,
    ) -> Tag:
        """
        更新标签

        Args:
            tag_id: 标签ID
            user: 操作用户
            其他参数: 要更新的字段

        Returns:
            Tag: 更新后的标签对象

        Raises:
            PermissionDenied: 权限不足
            ValueError: 参数错误
        """
        # 权限检查
        if not user.is_staff:
            raise PermissionDenied("只有管理员可以编辑标签")

        tag = Tag.objects.get(id=tag_id)

        with transaction.atomic():
            if name is not None:
                tag.name = name

            if slug is not None:
                tag.slug = slug

            if description is not None:
                tag.description = description

            if color is not None:
                tag.color = color

            if icon is not None:
                tag.icon = icon

            if background_url is not None:
                tag.background_url = background_url

            if position is not None:
                tag.position = position

            if parent_id is not None:
                # 检查父标签
                if parent_id == tag.id:
                    raise ValueError("标签不能设置自己为父标签")
                try:
                    parent = Tag.objects.get(id=parent_id)
                    # 检查是否会形成循环
                    if TagService._would_create_cycle(tag, parent):
                        raise ValueError("不能设置子标签为父标签（会形成循环）")
                    tag.parent = parent
                except Tag.DoesNotExist:
                    raise ValueError("父标签不存在")

            if is_hidden is not None:
                tag.is_hidden = is_hidden

            if is_restricted is not None:
                tag.is_restricted = is_restricted

            tag.save()
            return tag

    @staticmethod
    def _would_create_cycle(tag: Tag, new_parent: Tag) -> bool:
        """
        检查设置新父标签是否会形成循环

        Args:
            tag: 当前标签
            new_parent: 新的父标签

        Returns:
            bool: 是否会形成循环
        """
        current = new_parent
        while current:
            if current.id == tag.id:
                return True
            current = current.parent
        return False

    @staticmethod
    def delete_tag(tag_id: int, user: User) -> bool:
        """
        删除标签

        Args:
            tag_id: 标签ID
            user: 操作用户

        Returns:
            bool: 是否删除成功

        Raises:
            PermissionDenied: 权限不足
            ValueError: 参数错误
        """
        # 权限检查
        if not user.is_staff:
            raise PermissionDenied("只有管理员可以删除标签")

        tag = Tag.objects.get(id=tag_id)

        # 检查是否有子标签
        if Tag.objects.filter(parent=tag).exists():
            raise ValueError("该标签下还有子标签，请先删除或移动子标签")

        # 检查是否有讨论使用该标签
        if DiscussionTag.objects.filter(tag=tag).exists():
            raise ValueError("该标签下还有讨论，无法删除")

        with transaction.atomic():
            tag.delete()

        return True

    @staticmethod
    def get_popular_tags(limit: int = 10) -> List[Tag]:
        """
        获取热门标签

        Args:
            limit: 返回数量

        Returns:
            List[Tag]: 热门标签列表
        """
        tags = Tag.objects.filter(
            is_hidden=False
        ).order_by('-discussion_count', '-last_posted_at')[:limit]

        return list(tags)

    @staticmethod
    def refresh_tag_stats(tag_ids: Optional[List[int]] = None) -> None:
        """
        重新计算标签讨论数和最后发帖讨论。

        用于修复历史数据，也用于讨论创建、隐藏、删除后的统计同步。
        """
        queryset = Tag.objects.all()
        if tag_ids is not None:
            queryset = queryset.filter(id__in=tag_ids)

        for tag in queryset:
            discussion_links = DiscussionTag.objects.filter(
                tag=tag,
                discussion__hidden_at__isnull=True,
            ).select_related('discussion').order_by('-discussion__last_posted_at', '-discussion__id')

            latest_link = discussion_links.first()
            Tag.objects.filter(id=tag.id).update(
                discussion_count=discussion_links.count(),
                last_posted_at=latest_link.discussion.last_posted_at if latest_link else None,
                last_posted_discussion=latest_link.discussion if latest_link else None,
            )

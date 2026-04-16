"""
标签系统业务逻辑层
"""
from datetime import datetime
from typing import Optional, List
from django.db import transaction
from django.db.models import Q, F, Count, QuerySet
from django.core.exceptions import PermissionDenied
from apps.tags.models import Tag, DiscussionTag
from apps.users.models import User


class TagService:
    """标签服务"""

    ACTION_SCOPE_FIELD = {
        "view": "view_scope",
        "start_discussion": "start_discussion_scope",
        "reply": "reply_scope",
    }

    ACCESS_SCOPE_LABELS = {
        Tag.ACCESS_PUBLIC: "所有人",
        Tag.ACCESS_MEMBERS: "已登录用户",
        Tag.ACCESS_STAFF: "仅管理员",
    }
    ACCESS_SCOPE_LEVELS = {
        Tag.ACCESS_PUBLIC: 0,
        Tag.ACCESS_MEMBERS: 1,
        Tag.ACCESS_STAFF: 2,
    }

    @staticmethod
    def normalize_access_scope(scope: Optional[str], default: str) -> str:
        normalized = (scope or default).strip() if isinstance(scope, str) else default
        if normalized not in TagService.ACCESS_SCOPE_LABELS:
            raise ValueError("无效的标签访问级别")
        return normalized

    @staticmethod
    def has_scope_access(user: Optional[User], scope: str) -> bool:
        if user and (user.is_staff or user.is_superuser):
            return True
        if scope == Tag.ACCESS_PUBLIC:
            return True
        if scope == Tag.ACCESS_MEMBERS:
            return bool(user and user.is_authenticated)
        if scope == Tag.ACCESS_STAFF:
            return False
        return False

    @staticmethod
    def get_scope_label(scope: str) -> str:
        return TagService.ACCESS_SCOPE_LABELS.get(scope, "未知")

    @staticmethod
    def validate_scope_configuration(
        view_scope: str,
        start_discussion_scope: str,
        reply_scope: str,
    ) -> tuple[str, str, str]:
        normalized_view = TagService.normalize_access_scope(view_scope, Tag.ACCESS_PUBLIC)
        normalized_start = TagService.normalize_access_scope(start_discussion_scope, Tag.ACCESS_MEMBERS)
        normalized_reply = TagService.normalize_access_scope(reply_scope, Tag.ACCESS_MEMBERS)

        if TagService.ACCESS_SCOPE_LEVELS[normalized_start] < TagService.ACCESS_SCOPE_LEVELS[normalized_view]:
            raise ValueError("发帖权限不能比查看权限更宽松")

        if TagService.ACCESS_SCOPE_LEVELS[normalized_reply] < TagService.ACCESS_SCOPE_LEVELS[normalized_view]:
            raise ValueError("回帖权限不能比查看权限更宽松")

        return normalized_view, normalized_start, normalized_reply

    @staticmethod
    def can_view_tag(tag: Tag, user: Optional[User]) -> bool:
        return TagService.has_scope_access(user, tag.view_scope)

    @staticmethod
    def can_start_discussion_in_tag(tag: Tag, user: Optional[User]) -> bool:
        if tag.is_restricted and not (user and (user.is_staff or user.is_superuser)):
            return False
        return (
            TagService.can_view_tag(tag, user)
            and TagService.has_scope_access(user, tag.start_discussion_scope)
        )

    @staticmethod
    def can_reply_in_tag(tag: Tag, user: Optional[User]) -> bool:
        return (
            TagService.can_view_tag(tag, user)
            and TagService.has_scope_access(user, tag.reply_scope)
        )

    @staticmethod
    def can_view_discussion_tags(discussion, user: Optional[User]) -> bool:
        return all(TagService.can_view_tag(dt.tag, user) for dt in discussion.discussion_tags.all())

    @staticmethod
    def can_reply_in_discussion(discussion, user: Optional[User]) -> bool:
        tags = [dt.tag for dt in discussion.discussion_tags.all()]
        return all(TagService.can_reply_in_tag(tag, user) for tag in tags)

    @staticmethod
    def filter_tags_for_user(queryset: QuerySet, user: Optional[User], action: str = "view") -> QuerySet:
        if user and (user.is_staff or user.is_superuser):
            return queryset

        scope_field = TagService.ACTION_SCOPE_FIELD.get(action)
        if not scope_field:
            return queryset

        if user and user.is_authenticated:
            return queryset.exclude(**{scope_field: Tag.ACCESS_STAFF})

        return queryset.exclude(**{f"{scope_field}__in": [Tag.ACCESS_MEMBERS, Tag.ACCESS_STAFF]})

    @staticmethod
    def get_forbidden_tag_ids(user: Optional[User], action: str = "view") -> List[int]:
        allowed_tag_ids = TagService.filter_tags_for_user(
            Tag.objects.all(),
            user,
            action=action,
        ).values_list("id", flat=True)
        return list(Tag.objects.exclude(id__in=allowed_tag_ids).values_list("id", flat=True))

    @staticmethod
    def filter_discussions_for_user(queryset: QuerySet, user: Optional[User]) -> QuerySet:
        forbidden_tag_ids = TagService.get_forbidden_tag_ids(user, action="view")
        if not forbidden_tag_ids:
            return queryset

        return queryset.exclude(discussion_tags__tag_id__in=forbidden_tag_ids)

    @staticmethod
    def filter_posts_for_user(queryset: QuerySet, user: Optional[User]) -> QuerySet:
        forbidden_tag_ids = TagService.get_forbidden_tag_ids(user, action="view")
        if not forbidden_tag_ids:
            return queryset

        return queryset.exclude(discussion__discussion_tags__tag_id__in=forbidden_tag_ids)

    @staticmethod
    def validate_tag_selection(tag_ids: Optional[List[int]]) -> List[int]:
        if not tag_ids:
            return []
        normalized = []
        for tag_id in tag_ids:
            if not tag_id:
                continue
            if int(tag_id) not in normalized:
                normalized.append(int(tag_id))
        return normalized

    @staticmethod
    def get_tags_for_selection(tag_ids: Optional[List[int]]) -> List[Tag]:
        normalized_ids = TagService.validate_tag_selection(tag_ids)
        if not normalized_ids:
            return []

        tags_by_id = {
            tag.id: tag
            for tag in Tag.objects.filter(id__in=normalized_ids).select_related("parent")
        }
        if len(tags_by_id) != len(normalized_ids):
            raise ValueError("部分标签不存在")

        tags = [tags_by_id[tag_id] for tag_id in normalized_ids]
        primary_tags = [tag for tag in tags if tag.parent_id is None]
        secondary_tags = [tag for tag in tags if tag.parent_id is not None]

        if len(primary_tags) > 1:
            raise ValueError("当前最多只能选择 1 个主标签")

        if len(secondary_tags) > 1:
            raise ValueError("当前最多只能选择 1 个次标签")

        if secondary_tags and not primary_tags:
            raise ValueError("选择次标签时必须同时选择对应的主标签")

        if primary_tags and secondary_tags and secondary_tags[0].parent_id != primary_tags[0].id:
            raise ValueError("次标签必须与对应的主标签一起选择")

        if len(tags) > 2:
            raise ValueError("当前最多只能选择 2 个标签")

        return primary_tags + secondary_tags

    @staticmethod
    def ensure_can_start_discussion(user: User, tag_ids: Optional[List[int]]) -> List[Tag]:
        tags = TagService.get_tags_for_selection(tag_ids)

        for tag in tags:
            if not TagService.can_start_discussion_in_tag(tag, user):
                raise PermissionDenied(f"没有权限在标签“{tag.name}”下发起讨论")

        return tags

    @staticmethod
    def ensure_can_reply_in_discussion(user: User, discussion) -> None:
        for discussion_tag in discussion.discussion_tags.select_related("tag").all():
            if not TagService.can_reply_in_tag(discussion_tag.tag, user):
                raise PermissionDenied(f"没有权限在标签“{discussion_tag.tag.name}”下回复讨论")

    @staticmethod
    def validate_parent_assignment(tag: Optional[Tag], parent: Optional[Tag]) -> None:
        if parent is None:
            return

        if parent.parent_id is not None:
            raise ValueError("只能选择顶级标签作为父标签")

        if tag is not None:
            if tag.id == parent.id:
                raise ValueError("标签不能设置自己为父标签")
            if TagService._would_create_cycle(tag, parent):
                raise ValueError("不能设置子标签为父标签（会形成循环）")
            if tag.children.exists() and parent is not None:
                raise ValueError("已有子标签的标签不能再设置为子标签")

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
        view_scope: str = Tag.ACCESS_PUBLIC,
        start_discussion_scope: str = Tag.ACCESS_MEMBERS,
        reply_scope: str = Tag.ACCESS_MEMBERS,
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
            TagService.validate_parent_assignment(None, parent)

        normalized_view, normalized_start, normalized_reply = TagService.validate_scope_configuration(
            view_scope,
            start_discussion_scope,
            reply_scope,
        )

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
                view_scope=normalized_view,
                start_discussion_scope=normalized_start,
                reply_scope=normalized_reply,
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
            return Tag.objects.get(id=tag_id)
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
            return Tag.objects.get(slug=slug)
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
        view_scope: Optional[str] = None,
        start_discussion_scope: Optional[str] = None,
        reply_scope: Optional[str] = None,
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
        next_view_scope = tag.view_scope
        next_start_scope = tag.start_discussion_scope
        next_reply_scope = tag.reply_scope

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
                if parent_id in ("", 0, "0", None):
                    tag.parent = None
                else:
                    try:
                        parent = Tag.objects.get(id=parent_id)
                    except Tag.DoesNotExist:
                        raise ValueError("父标签不存在")
                    TagService.validate_parent_assignment(tag, parent)
                    tag.parent = parent

            if is_hidden is not None:
                tag.is_hidden = is_hidden

            if is_restricted is not None:
                tag.is_restricted = is_restricted

            if view_scope is not None:
                next_view_scope = view_scope

            if start_discussion_scope is not None:
                next_start_scope = start_discussion_scope

            if reply_scope is not None:
                next_reply_scope = reply_scope

            (
                tag.view_scope,
                tag.start_discussion_scope,
                tag.reply_scope,
            ) = TagService.validate_scope_configuration(
                next_view_scope,
                next_start_scope,
                next_reply_scope,
            )

            tag.save()
            return tag

    @staticmethod
    def move_tag(tag_id: int, direction: str, user: User) -> bool:
        if not user.is_staff:
            raise PermissionDenied("只有管理员可以调整标签排序")

        if direction not in {"up", "down"}:
            raise ValueError("无效的排序方向")

        tag = Tag.objects.get(id=tag_id)

        with transaction.atomic():
            siblings = list(
                Tag.objects.filter(parent_id=tag.parent_id).order_by("position", "name", "id")
            )
            current_index = next(
                (index for index, sibling in enumerate(siblings) if sibling.id == tag.id),
                None,
            )
            if current_index is None:
                raise ValueError("标签不存在于当前层级")

            target_index = current_index - 1 if direction == "up" else current_index + 1
            if target_index < 0 or target_index >= len(siblings):
                return False

            siblings[current_index], siblings[target_index] = siblings[target_index], siblings[current_index]

            for index, sibling in enumerate(siblings):
                sibling.position = index

            Tag.objects.bulk_update(siblings, ["position"])

        return True

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

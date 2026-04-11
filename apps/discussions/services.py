"""
讨论系统业务逻辑层
"""
from typing import Optional, List, Tuple
from django.db import transaction
from django.db.models import Q, F, Count
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.discussions.models import Discussion, DiscussionUser
from apps.posts.models import Post
from apps.users.models import User
from apps.tags.models import Tag, DiscussionTag


class DiscussionService:
    """讨论服务"""

    @staticmethod
    def create_discussion(
        title: str,
        content: str,
        user: User,
        tag_ids: Optional[List[int]] = None
    ) -> Discussion:
        """
        创建讨论

        Args:
            title: 讨论标题
            content: 第一条帖子内容
            user: 创建者
            tag_ids: 标签ID列表

        Returns:
            Discussion: 创建的讨论对象
        """
        with transaction.atomic():
            # 创建讨论
            discussion = Discussion.objects.create(
                title=title,
                user=user,
                last_posted_at=timezone.now(),
                last_posted_user=user,
            )

            # 创建第一条帖子
            first_post = Post.objects.create(
                discussion=discussion,
                number=1,
                user=user,
                content=content,
                content_html=DiscussionService._render_markdown(content),
                type='comment',
            )

            # 更新讨论的第一条帖子ID
            discussion.first_post_id = first_post.id
            discussion.last_post_id = first_post.id
            discussion.last_post_number = 1
            discussion.comment_count = 1
            discussion.participant_count = 1
            discussion.save()

            # 添加标签
            if tag_ids:
                tags = Tag.objects.filter(id__in=tag_ids)
                for tag in tags:
                    DiscussionTag.objects.create(discussion=discussion, tag=tag)

            # 更新用户统计
            user.discussion_count = F('discussion_count') + 1
            user.save(update_fields=['discussion_count'])

            # 创建用户阅读状态
            DiscussionUser.objects.create(
                discussion=discussion,
                user=user,
                last_read_at=timezone.now(),
                last_read_post_number=1,
                is_subscribed=user.preferences.get('follow_after_create', False),
            )

            return discussion

    @staticmethod
    def get_discussion_list(
        q: Optional[str] = None,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        subscription: Optional[str] = None,
        sort: str = 'latest',
        page: int = 1,
        limit: int = 20,
        user: Optional[User] = None,
    ) -> Tuple[List[Discussion], int]:
        """
        获取讨论列表

        Args:
            q: 搜索关键词
            tag: 标签slug
            author: 作者用户名
            sort: 排序方式
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Discussion], int]: (讨论列表, 总数)
        """
        queryset = Discussion.objects.select_related(
            'user', 'last_posted_user'
        ).prefetch_related('discussion_tags__tag')

        # 过滤隐藏的讨论
        queryset = queryset.filter(hidden_at__isnull=True)

        # 搜索
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(slug__icontains=q)
            )

        # 按标签过滤
        if tag:
            queryset = queryset.filter(tags__tag__slug=tag)

        # 按作者过滤
        if author:
            queryset = queryset.filter(user__username=author)

        # 订阅过滤
        if subscription == 'following':
            if not user or not user.is_authenticated:
                return [], 0

            queryset = queryset.filter(
                user_states__user=user,
                user_states__is_subscribed=True,
            )

        # 排序
        if sort == 'latest':
            queryset = queryset.order_by('-is_sticky', '-last_posted_at')
        elif sort == 'top':
            queryset = queryset.order_by('-is_sticky', '-comment_count', '-view_count')
        elif sort == 'oldest':
            queryset = queryset.order_by('-is_sticky', 'created_at')
        elif sort == 'newest':
            queryset = queryset.order_by('-is_sticky', '-created_at')
        else:
            queryset = queryset.order_by('-is_sticky', '-last_posted_at')

        # 分页
        queryset = queryset.distinct()
        total = queryset.count()
        offset = (page - 1) * limit
        discussions = list(queryset[offset:offset + limit])

        DiscussionService._attach_user_read_state(discussions, user)

        return discussions, total

    @staticmethod
    def get_discussion_by_id(discussion_id: int, user: Optional[User] = None) -> Optional[Discussion]:
        """
        获取讨论详情

        Args:
            discussion_id: 讨论ID
            user: 当前用户（用于更新阅读状态）

        Returns:
            Optional[Discussion]: 讨论对象
        """
        try:
            discussion = Discussion.objects.select_related(
                'user', 'last_posted_user'
            ).prefetch_related('discussion_tags__tag').get(id=discussion_id)

            # 增加浏览次数
            discussion.increment_view_count()

            # 更新用户阅读状态
            if user and user.is_authenticated:
                state, _ = DiscussionUser.objects.update_or_create(
                    discussion=discussion,
                    user=user,
                    defaults={
                        'last_read_at': timezone.now(),
                        'last_read_post_number': discussion.last_post_number or 0,
                    }
                )
                discussion.is_subscribed = state.is_subscribed
                discussion.last_read_at = state.last_read_at
                discussion.last_read_post_number = state.last_read_post_number
                discussion.unread_count = 0
                discussion.is_unread = False
            else:
                discussion.is_subscribed = False
                discussion.last_read_at = None
                discussion.last_read_post_number = 0
                discussion.unread_count = 0
                discussion.is_unread = False

            return discussion
        except Discussion.DoesNotExist:
            return None

    @staticmethod
    def _attach_user_read_state(discussions: List[Discussion], user: Optional[User]) -> None:
        if not discussions:
            return

        if not user or not user.is_authenticated:
            for discussion in discussions:
                discussion.is_subscribed = False
                discussion.last_read_at = None
                discussion.last_read_post_number = 0
                discussion.unread_count = 0
                discussion.is_unread = False
            return

        states = {
            state.discussion_id: state
            for state in DiscussionUser.objects.filter(
                user=user,
                discussion_id__in=[discussion.id for discussion in discussions],
            )
        }
        marked_all_as_read_at = getattr(user, 'marked_all_as_read_at', None)

        for discussion in discussions:
            state = states.get(discussion.id)
            last_read_at = state.last_read_at if state else None
            last_read_post_number = state.last_read_post_number if state else 0

            if (
                marked_all_as_read_at
                and discussion.last_posted_at
                and discussion.last_posted_at <= marked_all_as_read_at
            ):
                last_read_at = marked_all_as_read_at
                last_read_post_number = max(last_read_post_number, discussion.last_post_number or 0)

            discussion.is_subscribed = bool(state and state.is_subscribed)
            discussion.last_read_at = last_read_at
            discussion.last_read_post_number = last_read_post_number
            discussion.unread_count = max((discussion.last_post_number or 0) - last_read_post_number, 0)
            discussion.is_unread = discussion.unread_count > 0

    @staticmethod
    def mark_all_as_read(user: User):
        now = timezone.now()
        user.marked_all_as_read_at = now
        user.save(update_fields=['marked_all_as_read_at'])
        return now

    @staticmethod
    def get_subscription_state(discussion: Discussion, user: Optional[User]) -> bool:
        if not user or not user.is_authenticated:
            return False

        state = DiscussionUser.objects.filter(
            discussion=discussion,
            user=user,
            is_subscribed=True,
        ).exists()
        return state

    @staticmethod
    def subscribe_discussion(discussion_id: int, user: User) -> bool:
        discussion = Discussion.objects.get(id=discussion_id)
        state, _ = DiscussionUser.objects.get_or_create(
            discussion=discussion,
            user=user,
            defaults={
                'last_read_at': timezone.now(),
                'last_read_post_number': discussion.last_post_number or 0,
            }
        )
        if state.is_subscribed:
            return False
        state.is_subscribed = True
        state.save(update_fields=['is_subscribed'])
        return True

    @staticmethod
    def unsubscribe_discussion(discussion_id: int, user: User) -> bool:
        discussion = Discussion.objects.get(id=discussion_id)
        state, _ = DiscussionUser.objects.get_or_create(
            discussion=discussion,
            user=user,
            defaults={
                'last_read_at': timezone.now(),
                'last_read_post_number': discussion.last_post_number or 0,
            }
        )
        if not state.is_subscribed:
            return False
        state.is_subscribed = False
        state.save(update_fields=['is_subscribed'])
        return True

    @staticmethod
    def update_discussion(
        discussion_id: int,
        user: User,
        title: Optional[str] = None,
        is_locked: Optional[bool] = None,
        is_sticky: Optional[bool] = None,
        is_hidden: Optional[bool] = None,
    ) -> Discussion:
        """
        更新讨论

        Args:
            discussion_id: 讨论ID
            user: 操作用户
            title: 新标题
            is_locked: 是否锁定
            is_sticky: 是否置顶
            is_hidden: 是否隐藏

        Returns:
            Discussion: 更新后的讨论对象

        Raises:
            PermissionDenied: 权限不足
        """
        discussion = Discussion.objects.get(id=discussion_id)

        # 权限检查
        if not DiscussionService.can_edit_discussion(discussion, user):
            raise PermissionDenied("没有权限编辑此讨论")

        with transaction.atomic():
            if title is not None:
                discussion.title = title

            if is_locked is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限锁定/解锁讨论")
                discussion.is_locked = is_locked

            if is_sticky is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限置顶/取消置顶讨论")
                discussion.is_sticky = is_sticky

            if is_hidden is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限隐藏/显示讨论")
                if is_hidden:
                    discussion.hidden_at = timezone.now()
                    discussion.hidden_user = user
                else:
                    discussion.hidden_at = None
                    discussion.hidden_user = None

            discussion.save()
            return discussion

    @staticmethod
    def delete_discussion(discussion_id: int, user: User) -> bool:
        """
        删除讨论

        Args:
            discussion_id: 讨论ID
            user: 操作用户

        Returns:
            bool: 是否删除成功

        Raises:
            PermissionDenied: 权限不足
        """
        discussion = Discussion.objects.get(id=discussion_id)

        # 权限检查
        if not DiscussionService.can_delete_discussion(discussion, user):
            raise PermissionDenied("没有权限删除此讨论")

        with transaction.atomic():
            # 删除相关帖子
            Post.objects.filter(discussion=discussion).delete()

            # 删除讨论
            discussion.delete()

            # 更新用户统计
            if discussion.user:
                discussion.user.discussion_count = F('discussion_count') - 1
                discussion.user.save(update_fields=['discussion_count'])

        return True

    @staticmethod
    def can_edit_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以编辑讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if discussion.user_id == user.id:
            return True
        return False

    @staticmethod
    def can_delete_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以删除讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        # 只有管理员可以删除讨论
        return False

    @staticmethod
    def can_reply_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以回复讨论"""
        if not user or not user.is_authenticated:
            return False
        if discussion.is_locked and not user.is_staff:
            return False
        return True

    @staticmethod
    def _render_markdown(content: str) -> str:
        """
        渲染Markdown为HTML

        Args:
            content: Markdown内容

        Returns:
            str: HTML内容
        """
        from apps.core.markdown_service import MarkdownService
        return MarkdownService.render(content, sanitize=True)

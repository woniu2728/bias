"""
User service - 用户业务逻辑
"""
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime
import secrets

from .models import User, Group, Permission, EmailToken, PasswordToken
from apps.core.models import AuditLog
from apps.core.email_service import EmailService


class UserService:
    """用户服务类"""

    DEFAULT_MEMBER_FORUM_PERMISSIONS = {
        "viewForum",
        "viewUserList",
        "searchUsers",
        "startDiscussion",
        "discussion.reply",
        "discussion.editOwn",
        "discussion.deleteOwn",
    }

    STAFF_FORUM_PERMISSIONS = {
        "viewForum",
        "viewUserList",
        "searchUsers",
        "startDiscussion",
        "startDiscussionWithoutApproval",
        "discussion.reply",
        "replyWithoutApproval",
        "discussion.editOwn",
        "discussion.deleteOwn",
        "discussion.edit",
        "discussion.delete",
        "discussion.hide",
        "discussion.rename",
        "discussion.lock",
        "discussion.sticky",
        "user.edit",
        "user.suspend",
    }

    @staticmethod
    def build_suspension_notice(user: User, action_label: str = "") -> str:
        """构建封禁提示语"""
        parts = ["账号已被封禁"]

        if user.suspended_until:
            until = timezone.localtime(user.suspended_until).strftime("%Y-%m-%d %H:%M")
            parts.append(f"至 {until}")

        message = " ".join(parts)

        if user.suspend_message:
            return f"{message}。{user.suspend_message}"
        if action_label:
            return f"{message}，暂时无法{action_label}"
        return message

    @staticmethod
    def ensure_not_suspended(user: User, action_label: str = ""):
        """禁止被封禁用户执行写操作"""
        if user and user.is_suspended:
            raise PermissionDenied(UserService.build_suspension_notice(user, action_label))

    @staticmethod
    def ensure_email_confirmed(user: User, action_label: str = ""):
        """禁止未验证邮箱的普通用户执行需要实名邮箱的写操作"""
        if not user or not user.is_authenticated:
            return
        if user.is_staff or user.is_superuser:
            return
        if user.is_email_confirmed:
            return

        if action_label:
            raise PermissionDenied(f"请先完成邮箱验证后再{action_label}")
        raise PermissionDenied("请先完成邮箱验证")

    @staticmethod
    def get_forum_permission_set(user: User):
        if not user or not user.is_authenticated:
            return set()

        cached_permissions = getattr(user, "_forum_permission_cache", None)
        if cached_permissions is not None:
            return cached_permissions

        if user.is_staff or user.is_superuser:
            permissions = set(UserService.STAFF_FORUM_PERMISSIONS)
            user._forum_permission_cache = permissions
            return permissions

        prefetched_groups = getattr(user, "_prefetched_objects_cache", {}).get("user_groups")
        if prefetched_groups is not None:
            group_ids = [group.id for group in prefetched_groups]
        else:
            group_ids = list(user.user_groups.values_list("id", flat=True))

        if not group_ids:
            permissions = set(UserService.DEFAULT_MEMBER_FORUM_PERMISSIONS)
        else:
            permissions = set(
                Permission.objects.filter(group_id__in=group_ids).values_list("permission", flat=True)
            )

        user._forum_permission_cache = permissions
        return permissions

    @staticmethod
    def get_serialized_forum_permissions(user: User):
        return sorted(UserService.get_forum_permission_set(user))

    @staticmethod
    def has_forum_permission(user: User, permission_names) -> bool:
        if not user or not user.is_authenticated:
            return False

        if isinstance(permission_names, str):
            permission_names = [permission_names]

        permissions = UserService.get_forum_permission_set(user)
        return any(permission in permissions for permission in permission_names)

    @staticmethod
    def ensure_forum_permission(user: User, permission_names, message: str):
        if not UserService.has_forum_permission(user, permission_names):
            raise PermissionDenied(message)

    @staticmethod
    def requires_content_approval(user: User, bypass_permission: str) -> bool:
        """只有在后台显式配置了免审核权限后，未命中该权限的用户才需进入审核队列"""
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return False

        if not Permission.objects.filter(permission=bypass_permission).exists():
            return False

        return not UserService.has_forum_permission(user, bypass_permission)

    @staticmethod
    def create_user(username: str, email: str, password: str) -> User:
        """创建用户"""
        with transaction.atomic():
            # 检查用户名是否存在
            if User.objects.filter(username=username).exists():
                raise ValueError("用户名已存在")

            # 检查邮箱是否存在
            if User.objects.filter(email=email).exists():
                raise ValueError("邮箱已被使用")

            # 创建用户
            user = User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                is_email_confirmed=False,
            )

            # 添加到默认用户组（Member）
            try:
                member_group = Group.objects.get(name='Member')
                member_group.users.add(user)
            except Group.DoesNotExist:
                pass

            # 创建邮箱验证令牌
            UserService.create_email_verification_token(user)

            return user

    @staticmethod
    def authenticate_user(identification: str, password: str) -> User:
        """验证用户登录"""
        # 尝试用户名登录
        user = User.objects.filter(username=identification).first()

        # 如果用户名不存在，尝试邮箱登录
        if not user:
            user = User.objects.filter(email=identification).first()

        # 验证密码
        if user and check_password(password, user.password):
            # 检查是否被封禁
            if user.is_suspended:
                raise ValueError(UserService.build_suspension_notice(user))

            # 更新最后登录时间
            user.last_seen_at = timezone.now()
            user.save(update_fields=['last_seen_at'])

            return user

        raise ValueError("用户名或密码错误")

    @staticmethod
    def update_user(user: User, **kwargs) -> User:
        """更新用户信息"""
        allowed_fields = ['display_name', 'bio', 'email', 'avatar_url']

        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                # 如果更新邮箱，需要重新验证
                if field == 'email' and value != user.email:
                    if User.objects.filter(email=value).exists():
                        raise ValueError("邮箱已被使用")
                    user.is_email_confirmed = False
                    UserService.create_email_verification_token(user, value)

                setattr(user, field, value)

        user.save()
        return user

    @staticmethod
    def change_password(user: User, old_password: str, new_password: str) -> bool:
        """修改密码"""
        if not check_password(old_password, user.password):
            raise ValueError("原密码错误")

        user.password = make_password(new_password)
        user.save(update_fields=['password'])

        # 记录审计日志
        AuditLog.objects.create(
            user=user,
            action='password_changed',
            target_type='User',
            target_id=user.id,
        )

        return True

    @staticmethod
    def create_email_verification_token(user: User, email: str = None) -> EmailToken:
        """创建邮箱验证令牌"""
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)

        email_token = EmailToken.objects.create(
            token=token,
            email=email or user.email,
            user=user,
            expires_at=expires_at,
        )

        EmailService.queue_verification_email(
            user_email=email_token.email,
            username=user.display_name or user.username,
            token=token,
        )

        return email_token

    @staticmethod
    def verify_email(token: str) -> User:
        """验证邮箱"""
        try:
            email_token = EmailToken.objects.get(token=token)

            # 检查是否过期
            if timezone.now() > email_token.expires_at:
                raise ValueError("验证链接已过期")

            user = email_token.user
            user.email = email_token.email
            user.is_email_confirmed = True
            user.save(update_fields=['email', 'is_email_confirmed'])

            # 删除已使用的令牌
            email_token.delete()

            return user

        except EmailToken.DoesNotExist:
            raise ValueError("无效的验证令牌")

    @staticmethod
    def resend_email_verification(user: User) -> EmailToken:
        """重新发送当前邮箱的验证邮件"""
        if user.is_email_confirmed:
            raise ValueError("当前邮箱已经验证")
        if not user.email:
            raise ValueError("当前账号没有可验证的邮箱")

        user.email_tokens.all().delete()
        return UserService.create_email_verification_token(user, user.email)

    @staticmethod
    def create_password_reset_token(email: str) -> PasswordToken:
        """创建密码重置令牌"""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValueError("邮箱不存在")

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=1)

        password_token = PasswordToken.objects.create(
            token=token,
            user=user,
            expires_at=expires_at,
        )

        email_sent = EmailService.queue_password_reset_email(
            user_email=user.email,
            username=user.display_name or user.username,
            token=token,
        )

        if not email_sent and not settings.DEBUG:
            raise ValueError("重置密码邮件发送失败")

        return password_token

    @staticmethod
    def reset_password(token: str, new_password: str) -> User:
        """重置密码"""
        try:
            password_token = PasswordToken.objects.get(token=token)

            # 检查是否过期
            if timezone.now() > password_token.expires_at:
                raise ValueError("重置链接已过期")

            user = password_token.user
            user.password = make_password(new_password)
            user.save(update_fields=['password'])

            # 删除已使用的令牌
            password_token.delete()

            # 记录审计日志
            AuditLog.objects.create(
                user=user,
                action='password_reset',
                target_type='User',
                target_id=user.id,
            )

            return user

        except PasswordToken.DoesNotExist:
            raise ValueError("无效的重置令牌")

    @staticmethod
    def suspend_user(user: User, until: datetime, reason: str = "", message: str = "") -> User:
        """封禁用户"""
        user.suspended_until = until
        user.suspend_reason = reason
        user.suspend_message = message
        user.save(update_fields=['suspended_until', 'suspend_reason', 'suspend_message'])

        return user

    @staticmethod
    def unsuspend_user(user: User) -> User:
        """解除封禁"""
        user.suspended_until = None
        user.suspend_reason = ""
        user.suspend_message = ""
        user.save(update_fields=['suspended_until', 'suspend_reason', 'suspend_message'])

        return user

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from extensions.users.backend.models import User, Group, Permission, AccessToken, EmailToken, PasswordToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """用户管理"""
    list_display = ['username', 'email', 'display_name', 'is_email_confirmed', 'joined_at', 'is_staff']
    list_filter = ['is_email_confirmed', 'is_staff', 'is_superuser', 'joined_at']
    search_fields = ['username', 'email', 'display_name']
    ordering = ['-joined_at']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('display_name', 'email', 'bio', 'avatar_url')}),
        ('状态', {'fields': ('is_email_confirmed', 'is_active', 'is_staff', 'is_superuser')}),
        ('统计', {'fields': ('discussion_count', 'comment_count')}),
        ('封禁', {'fields': ('suspended_until', 'suspend_reason', 'suspend_message')}),
        ('时间', {'fields': ('joined_at', 'last_seen_at', 'marked_all_as_read_at')}),
        ('偏好', {'fields': ('preferences',)}),
    )

    readonly_fields = ['joined_at', 'last_seen_at']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """用户组管理"""
    list_display = ['name', 'name_singular', 'name_plural', 'color', 'is_hidden']
    list_filter = ['is_hidden']
    search_fields = ['name']
    filter_horizontal = ['users']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """权限管理"""
    list_display = ['group', 'permission', 'created_at']
    list_filter = ['group']
    search_fields = ['permission']


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    """访问令牌管理"""
    list_display = ['user', 'type', 'title', 'created_at', 'expires_at']
    list_filter = ['type', 'created_at']
    search_fields = ['user__username', 'token']
    readonly_fields = ['token', 'created_at']


@admin.register(EmailToken)
class EmailTokenAdmin(admin.ModelAdmin):
    """邮箱验证令牌管理"""
    list_display = ['user', 'email', 'created_at', 'expires_at']
    search_fields = ['user__username', 'email', 'token']
    readonly_fields = ['token', 'created_at']


@admin.register(PasswordToken)
class PasswordTokenAdmin(admin.ModelAdmin):
    """密码重置令牌管理"""
    list_display = ['user', 'created_at', 'expires_at']
    search_fields = ['user__username', 'token']
    readonly_fields = ['token', 'created_at']

"""
讨论系统Django Admin配置
"""
from django.contrib import admin
from extensions.discussions.backend.models import Discussion, DiscussionUser


@admin.register(Discussion)
class DiscussionAdmin(admin.ModelAdmin):
    """讨论管理"""
    list_display = [
        'id', 'title', 'user', 'comment_count', 'view_count',
        'is_sticky', 'is_locked', 'is_hidden', 'created_at'
    ]
    list_filter = ['is_sticky', 'is_locked', 'created_at']
    search_fields = ['title', 'slug', 'user__username']
    readonly_fields = [
        'slug', 'created_at', 'updated_at', 'last_posted_at',
        'comment_count', 'participant_count', 'view_count'
    ]
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'slug', 'user')
        }),
        ('状态', {
            'fields': ('is_sticky', 'is_locked', 'is_private')
        }),
        ('隐藏信息', {
            'fields': ('hidden_at', 'hidden_user')
        }),
        ('统计数据', {
            'fields': ('comment_count', 'participant_count', 'view_count')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at', 'last_posted_at')
        }),
        ('最后发帖', {
            'fields': ('last_posted_user', 'last_post_id', 'last_post_number')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']


@admin.register(DiscussionUser)
class DiscussionUserAdmin(admin.ModelAdmin):
    """讨论-用户状态管理"""
    list_display = [
        'id', 'discussion', 'user', 'last_read_post_number',
        'is_subscribed', 'last_read_at'
    ]
    list_filter = ['is_subscribed', 'last_read_at']
    search_fields = ['discussion__title', 'user__username']
    readonly_fields = ['created_at']
    ordering = ['-last_read_at']

"""
帖子系统Django Admin配置
"""
from django.contrib import admin
from extensions.posts.backend.models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """帖子管理"""
    list_display = [
        'id', 'discussion', 'number', 'user', 'type',
        'is_hidden', 'created_at'
    ]
    list_filter = ['type', 'is_private', 'created_at']
    search_fields = ['content', 'discussion__title', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'edited_at']
    fieldsets = (
        ('基本信息', {
            'fields': ('discussion', 'number', 'user', 'type')
        }),
        ('内容', {
            'fields': ('content', 'content_html')
        }),
        ('状态', {
            'fields': ('is_private',)
        }),
        ('编辑信息', {
            'fields': ('edited_at', 'edited_user')
        }),
        ('隐藏信息', {
            'fields': ('hidden_at', 'hidden_user')
        }),
        ('其他', {
            'fields': ('ip_address', 'created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']


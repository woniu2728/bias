"""
通知系统Django Admin配置
"""
from django.contrib import admin
from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """通知管理"""
    list_display = [
        'id', 'user', 'from_user', 'type', 'subject_type',
        'subject_id', 'is_read', 'created_at'
    ]
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['user__username', 'from_user__username', 'type']
    readonly_fields = ['created_at', 'read_at']
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'from_user', 'type')
        }),
        ('主体', {
            'fields': ('subject_type', 'subject_id')
        }),
        ('数据', {
            'fields': ('data',)
        }),
        ('状态', {
            'fields': ('is_read', 'read_at')
        }),
        ('时间', {
            'fields': ('created_at',)
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_per_page = 50

    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        """批量标记为已读"""
        from django.utils import timezone
        from apps.notifications.services import NotificationService

        user_ids = list(queryset.values_list('user_id', flat=True).distinct())
        count = queryset.update(is_read=True, read_at=timezone.now())
        NotificationService.invalidate_unread_counts(user_ids)
        self.message_user(request, f'成功标记 {count} 条通知为已读')
    mark_as_read.short_description = '标记为已读'

    def mark_as_unread(self, request, queryset):
        """批量标记为未读"""
        from apps.notifications.services import NotificationService

        user_ids = list(queryset.values_list('user_id', flat=True).distinct())
        count = queryset.update(is_read=False, read_at=None)
        NotificationService.invalidate_unread_counts(user_ids)
        self.message_user(request, f'成功标记 {count} 条通知为未读')
    mark_as_unread.short_description = '标记为未读'

    def has_add_permission(self, request):
        """禁止手动添加通知"""
        return False

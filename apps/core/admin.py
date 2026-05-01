from django.contrib import admin

from apps.core.models import AuditLog, Setting


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ["key", "updated_at"]
    search_fields = ["key", "value"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "action", "target_type", "target_id", "ip_address"]
    list_filter = ["action", "target_type", "created_at"]
    search_fields = ["action", "target_type", "target_id", "user__username"]
    readonly_fields = [
        "user",
        "action",
        "target_type",
        "target_id",
        "ip_address",
        "user_agent",
        "data",
        "created_at",
    ]

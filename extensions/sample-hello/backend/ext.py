from __future__ import annotations

from apps.core.extensions import (
    AdminNavigationExtender,
    FrontendExtender,
    LifecycleExtender,
    RuntimeActionsExtender,
    SettingsExtender,
)
from apps.core.extensions.backend import _build_runtime_action_definition, _build_setting_field_definition

EXTENSION_ID = "sample-hello"
EXTENSION_NAME = "Sample Hello"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/sample-hello/frontend/admin/index.js",
            forum_entry="extensions/sample-hello/frontend/forum/index.js",
        ),
        SettingsExtender(fields=(
            _build_setting_field_definition({
                "key": "welcome_message",
                "label": "欢迎语",
                "type": "text",
                "default": "欢迎使用 Sample Hello",
                "placeholder": "输入后台卡片展示的欢迎语",
                "help_text": "该设置项用于验证扩展设置协议的统一读写。",
                "order": 10,
            }),
            _build_setting_field_definition({
                "key": "card_tone",
                "label": "卡片风格",
                "type": "select",
                "default": "primary",
                "help_text": "切换示例设置页卡片强调色。",
                "options": (
                    {"value": "primary", "label": "主色"},
                    {"value": "warm", "label": "暖色"},
                    {"value": "neutral", "label": "中性色"},
                ),
                "order": 20,
            }),
            _build_setting_field_definition({
                "key": "show_runtime_tips",
                "label": "显示运行提示",
                "type": "boolean",
                "default": True,
                "help_text": "控制设置页底部是否展示运行时提示。",
                "order": 30,
            }),
        )),
        RuntimeActionsExtender(actions=(
            _build_runtime_action_definition({
                "key": "rebuild-cache",
                "label": "刷新缓存",
                "hook": "run_rebuild_cache",
                "requires_enabled": True,
                "requires_installed": True,
                "order": 5,
            }),
        ), generated_page=True),
        AdminNavigationExtender(generated_permissions_page=True),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def install(context):
    return {
        "status": "ok",
        "status_label": "已完成",
        "message": f"{context.extension_name} 安装生命周期已执行。",
        "details": {
            "extension_id": context.extension_id,
            "migration_namespace": context.migration_namespace,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": f"{context.extension_name} 启用生命周期已执行。",
        "details": {
            "booted": True,
        },
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": f"{context.extension_name} 停用生命周期已执行。",
        "details": {
            "booted": False,
        },
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已完成",
        "message": f"{context.extension_name} 卸载生命周期已执行。",
        "details": {
            "cleanup": "installation-record",
        },
    }


def run_rebuild_cache(context):
    return {
        "status": "ok",
        "status_label": "已刷新",
        "message": f"{context.extension_name} 的运行缓存已刷新。",
        "details": {
            "cache": "rebuilt",
        },
    }


def run_migrations(context):
    return {
        "status": "ok",
        "status_label": "已执行",
        "message": f"{context.extension_name} 的扩展迁移已执行。",
        "details": {
            "migration_namespace": context.migration_namespace,
            "applied_steps": ["bootstrap", "seed"],
        },
    }

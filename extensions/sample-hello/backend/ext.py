from __future__ import annotations

EXTENSION_ID = "sample-hello"
EXTENSION_NAME = "Sample Hello"


def run_install(context):
    return {
        "status": "ok",
        "status_label": "已完成",
        "message": f"{context.extension_name} 安装钩子已执行。",
        "details": {
            "extension_id": context.extension_id,
            "migration_namespace": context.migration_namespace,
        },
    }


def run_enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": f"{context.extension_name} 启用钩子已执行。",
        "details": {
            "booted": True,
        },
    }


def run_disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": f"{context.extension_name} 停用钩子已执行。",
        "details": {
            "booted": False,
        },
    }


def run_uninstall(context):
    return {
        "status": "ok",
        "status_label": "已完成",
        "message": f"{context.extension_name} 卸载钩子已执行。",
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

from apps.core.extensions import ApiRoutesExtender, FrontendExtender, LifecycleExtender, SettingsExtender
from apps.core.extensions.backend import _build_setting_field_definition
from extensions.uploads.backend.api import router as uploads_router


EXTENSION_ID = "uploads"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/uploads/frontend/admin/index.js",
            forum_entry="extensions/uploads/frontend/forum/index.js",
        ),
        ApiRoutesExtender(
            mounts=(("", uploads_router),),
            tags=("Uploads",),
        ),
        SettingsExtender(fields=setting_definitions())
        .default("attachments_dir", "attachments")
        .default("attachment_max_size_mb", 10),
        SettingsExtender(generated_page=False)
        .default("advanced.upload_site_asset_max_size_mb", 2),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def setting_definitions():
    return (
        _build_setting_field_definition({
            "key": "attachments_dir",
            "label": "附件目录",
            "type": "text",
            "default": "attachments",
            "help_text": "附件对象保存目录，支持多级路径。",
            "required": True,
            "order": 5,
        }),
        _build_setting_field_definition({
            "key": "attachment_max_size_mb",
            "label": "附件最大体积（MB）",
            "type": "number",
            "default": 10,
            "help_text": "限制 Composer 附件上传大小，允许范围 1-100MB。",
            "required": True,
            "order": 10,
        }),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Uploads 扩展已安装。",
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Uploads 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Uploads 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Uploads 扩展已卸载。",
    }

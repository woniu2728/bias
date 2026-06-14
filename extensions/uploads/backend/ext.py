from apps.core.extensions import ApiRoutesExtender, FrontendExtender, LifecycleExtender, SettingsExtender, setting_field
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
        build_storage_settings_extender(),
        LifecycleExtender(),
    ]


def setting_definitions():
    return (
        setting_field({
            "key": "attachments_dir",
            "label": "附件目录",
            "type": "text",
            "default": "attachments",
            "help_text": "附件对象保存目录，支持多级路径。",
            "required": True,
            "order": 5,
        }),
        setting_field({
            "key": "attachment_max_size_mb",
            "label": "附件最大体积（MB）",
            "type": "number",
            "default": 10,
            "help_text": "限制 Composer 附件上传大小，允许范围 1-100MB。",
            "required": True,
            "order": 10,
        }),
    )


def build_storage_settings_extender():
    return (
        SettingsExtender(generated_page=False)
        .default("advanced.storage_driver", "local")
        .default("advanced.storage_local_path", "")
        .default("advanced.storage_local_base_url", "/media/")
        .default("advanced.storage_s3_bucket", "")
        .default("advanced.storage_s3_region", "")
        .default("advanced.storage_s3_endpoint", "")
        .default("advanced.storage_s3_access_key_id", "")
        .default("advanced.storage_s3_secret_access_key", "")
        .default("advanced.storage_s3_public_url", "")
        .default("advanced.storage_s3_object_prefix", "")
        .default("advanced.storage_s3_path_style", False)
        .default("advanced.storage_r2_bucket", "")
        .default("advanced.storage_r2_endpoint", "")
        .default("advanced.storage_r2_access_key_id", "")
        .default("advanced.storage_r2_secret_access_key", "")
        .default("advanced.storage_r2_public_url", "")
        .default("advanced.storage_r2_object_prefix", "")
        .default("advanced.storage_oss_bucket", "")
        .default("advanced.storage_oss_endpoint", "")
        .default("advanced.storage_oss_access_key_id", "")
        .default("advanced.storage_oss_access_key_secret", "")
        .default("advanced.storage_oss_public_url", "")
        .default("advanced.storage_oss_object_prefix", "")
        .default("advanced.storage_imagebed_endpoint", "")
        .default("advanced.storage_imagebed_method", "POST")
        .default("advanced.storage_imagebed_file_field", "file")
        .default("advanced.storage_imagebed_headers", "{}")
        .default("advanced.storage_imagebed_form_data", "{}")
        .default("advanced.storage_imagebed_url_path", "data.url")
        .default("advanced.upload_site_asset_max_size_mb", 2)
    )

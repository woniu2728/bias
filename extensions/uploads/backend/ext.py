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
        .default("attachment_max_size_mb", 10)
        .default("avatars_dir", "avatars")
        .default("avatar_max_size_mb", 2)
        .default("upload_site_asset_max_size_mb", 2),
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
        setting_field({
            "key": "upload_site_asset_max_size_mb",
            "label": "站点资源最大体积（MB）",
            "type": "number",
            "default": 2,
            "help_text": "限制 Logo 和 Favicon 上传大小，允许范围 1-100MB。",
            "required": True,
            "order": 15,
        }),
        setting_field({
            "key": "avatars_dir",
            "label": "头像目录",
            "type": "text",
            "default": "avatars",
            "help_text": "头像和缩略图对象保存目录，支持多级路径。",
            "required": True,
            "order": 18,
        }),
        setting_field({
            "key": "avatar_max_size_mb",
            "label": "头像最大体积（MB）",
            "type": "number",
            "default": 2,
            "help_text": "限制用户头像上传大小，允许范围 1-100MB。",
            "required": True,
            "order": 19,
        }),
        setting_field({
            "key": "storage_driver",
            "label": "存储驱动",
            "type": "select",
            "default": "local",
            "help_text": "头像、站点资源和 Composer 附件上传都会使用这里的运行时存储配置。",
            "options": [
                {"value": "local", "label": "本地存储"},
                {"value": "s3", "label": "Amazon S3 / S3 兼容"},
                {"value": "r2", "label": "Cloudflare R2"},
                {"value": "oss", "label": "阿里云 OSS"},
                {"value": "imagebed", "label": "通用图床"},
            ],
            "order": 20,
        }),
        setting_field({"key": "storage_local_path", "label": "本地保存目录", "type": "text", "default": "", "placeholder": "D:\\data\\bias\\media", "help_text": "可填写绝对路径，也可填写相对项目根目录的路径。", "order": 30}),
        setting_field({"key": "storage_local_base_url", "label": "本地访问基地址", "type": "text", "default": "/media/", "placeholder": "/media/", "help_text": "上传完成后生成给前台的 URL 前缀。", "order": 40}),
        setting_field({"key": "storage_s3_bucket", "label": "S3 Bucket", "type": "text", "default": "", "order": 50}),
        setting_field({"key": "storage_s3_region", "label": "S3 Region", "type": "text", "default": "", "placeholder": "ap-southeast-1", "order": 60}),
        setting_field({"key": "storage_s3_endpoint", "label": "S3 Endpoint", "type": "text", "default": "", "placeholder": "https://s3.amazonaws.com", "help_text": "使用 MinIO、Wasabi 等兼容服务时填写自定义 Endpoint。", "order": 70}),
        setting_field({"key": "storage_s3_access_key_id", "label": "S3 Access Key ID", "type": "text", "default": "", "order": 80}),
        setting_field({"key": "storage_s3_secret_access_key", "label": "S3 Secret Access Key", "type": "text", "default": "", "order": 90}),
        setting_field({"key": "storage_s3_public_url", "label": "S3 公共访问 URL", "type": "text", "default": "", "placeholder": "https://cdn.example.com", "help_text": "如留空，系统会按标准 S3 域名尝试拼接。", "order": 100}),
        setting_field({"key": "storage_s3_object_prefix", "label": "S3 对象前缀", "type": "text", "default": "", "placeholder": "bias", "order": 110}),
        setting_field({"key": "storage_s3_path_style", "label": "S3 使用 Path Style", "type": "boolean", "default": False, "help_text": "兼容部分 S3 服务或自建对象存储。", "order": 120}),
        setting_field({"key": "storage_r2_bucket", "label": "R2 Bucket", "type": "text", "default": "", "order": 130}),
        setting_field({"key": "storage_r2_endpoint", "label": "R2 Endpoint", "type": "text", "default": "", "placeholder": "https://<accountid>.r2.cloudflarestorage.com", "order": 140}),
        setting_field({"key": "storage_r2_access_key_id", "label": "R2 Access Key ID", "type": "text", "default": "", "order": 150}),
        setting_field({"key": "storage_r2_secret_access_key", "label": "R2 Secret Access Key", "type": "text", "default": "", "order": 160}),
        setting_field({"key": "storage_r2_public_url", "label": "R2 公共访问 URL / CDN 域名", "type": "text", "default": "", "placeholder": "https://pub-xxx.r2.dev", "help_text": "R2 通常需要单独的公开域名，否则前台生成的附件链接不可访问。", "order": 170}),
        setting_field({"key": "storage_r2_object_prefix", "label": "R2 对象前缀", "type": "text", "default": "", "placeholder": "bias", "order": 180}),
        setting_field({"key": "storage_oss_bucket", "label": "OSS Bucket", "type": "text", "default": "", "order": 190}),
        setting_field({"key": "storage_oss_endpoint", "label": "OSS Endpoint", "type": "text", "default": "", "placeholder": "oss-cn-hangzhou.aliyuncs.com", "order": 200}),
        setting_field({"key": "storage_oss_access_key_id", "label": "OSS Access Key ID", "type": "text", "default": "", "order": 210}),
        setting_field({"key": "storage_oss_access_key_secret", "label": "OSS Access Key Secret", "type": "text", "default": "", "order": 220}),
        setting_field({"key": "storage_oss_public_url", "label": "OSS 公共访问 URL", "type": "text", "default": "", "placeholder": "https://cdn.example.com", "help_text": "如留空，将按 Bucket + Endpoint 生成标准 OSS 访问地址。", "order": 230}),
        setting_field({"key": "storage_oss_object_prefix", "label": "OSS 对象前缀", "type": "text", "default": "", "placeholder": "bias", "order": 240}),
        setting_field({"key": "storage_imagebed_endpoint", "label": "图床上传接口地址", "type": "text", "default": "", "placeholder": "https://example.com/api/upload", "order": 250}),
        setting_field({
            "key": "storage_imagebed_method",
            "label": "图床请求方法",
            "type": "select",
            "default": "POST",
            "options": [
                {"value": "POST", "label": "POST"},
                {"value": "PUT", "label": "PUT"},
                {"value": "PATCH", "label": "PATCH"},
            ],
            "order": 260,
        }),
        setting_field({"key": "storage_imagebed_file_field", "label": "图床文件字段名", "type": "text", "default": "file", "placeholder": "file", "order": 270}),
        setting_field({"key": "storage_imagebed_headers", "label": "图床请求头 JSON", "type": "textarea", "default": "{}", "placeholder": "{\"Authorization\":\"Bearer token\"}", "order": 280}),
        setting_field({"key": "storage_imagebed_form_data", "label": "图床额外表单参数 JSON", "type": "textarea", "default": "{}", "placeholder": "{\"album\":\"forum\"}", "order": 290}),
        setting_field({"key": "storage_imagebed_url_path", "label": "图床响应 URL 路径", "type": "text", "default": "data.url", "placeholder": "data.url", "help_text": "支持点路径，例如 data.url、result.images.0.url。", "order": 300}),
    )

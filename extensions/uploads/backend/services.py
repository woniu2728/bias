import os
import uuid

from apps.core.extensions.platform import FileUploadService
from apps.core.extensions.platform import get_extension_settings
from apps.core.extensions.platform import get_storage_backend


ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
ALLOWED_LOGO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")
ALLOWED_FAVICON_EXTENSIONS = (".ico", ".png", ".svg", ".webp")
ALLOWED_ATTACHMENT_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".zip",
    ".rar",
    ".7z",
)


class UploadService:
    MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
    MAX_SITE_ASSET_SIZE = 2 * 1024 * 1024

    @staticmethod
    def get_upload_policy() -> dict:
        return {
            "attachment_max_size_mb": UploadService.get_attachment_upload_limit_mb(),
            "allowed_image_extensions": ALLOWED_IMAGE_EXTENSIONS,
            "allowed_attachment_extensions": ALLOWED_ATTACHMENT_EXTENSIONS,
        }

    @staticmethod
    def upload_attachment(file, user_id: int):
        UploadService._validate_attachment(file, UploadService.get_attachment_upload_limit_bytes())

        ext = os.path.splitext(file.name)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        backend = get_upload_storage_backend()
        content = FileUploadService.read_uploaded_file(file)
        object_key = backend.build_user_key(UploadService.get_attachments_dir(), user_id, filename)
        file_url = backend.save_bytes(
            object_key,
            content,
            content_type=backend.guess_content_type(filename, file.content_type),
        )

        file_info = {
            "original_name": file.name,
            "size": file.size,
            "mime_type": file.content_type,
            "hash": FileUploadService.calculate_file_hash(content),
        }
        return file_url, file_info

    @staticmethod
    def is_image_extension(ext: str) -> bool:
        return str(ext or "").lower() in ALLOWED_IMAGE_EXTENSIONS

    @staticmethod
    def upload_site_asset(file, asset_type: str):
        normalized_type = str(asset_type or "").strip().lower()
        ext = os.path.splitext(file.name)[1].lower()

        if normalized_type == "logo":
            allowed_extensions = ALLOWED_LOGO_EXTENSIONS
        elif normalized_type == "favicon":
            allowed_extensions = ALLOWED_FAVICON_EXTENSIONS
        else:
            raise ValueError("不支持的站点资源类型")

        UploadService._validate_site_asset(
            file,
            allowed_extensions,
            UploadService.get_site_asset_upload_limit_bytes(),
        )

        filename = f"{uuid.uuid4().hex}{ext}"
        backend = get_upload_storage_backend()
        content = FileUploadService.read_uploaded_file(file)
        object_key = backend.join_key("appearance", normalized_type, filename)
        file_url = backend.save_bytes(
            object_key,
            content,
            content_type=backend.guess_content_type(filename, file.content_type),
        )

        file_info = {
            "original_name": file.name,
            "size": file.size,
            "mime_type": file.content_type,
            "hash": FileUploadService.calculate_file_hash(content),
        }
        return file_url, file_info

    @staticmethod
    def get_attachment_upload_limit_mb() -> int:
        settings_data = get_extension_settings("uploads")
        return FileUploadService._normalize_upload_size_mb(
            settings_data.get("attachment_max_size_mb"),
            UploadService.MAX_ATTACHMENT_SIZE,
        )

    @staticmethod
    def get_attachment_upload_limit_bytes() -> int:
        return int(UploadService.get_attachment_upload_limit_mb() * 1024 * 1024)

    @staticmethod
    def get_site_asset_upload_limit_mb() -> int:
        settings_data = get_uploads_settings()
        return FileUploadService._normalize_upload_size_mb(
            settings_data.get("upload_site_asset_max_size_mb"),
            UploadService.MAX_SITE_ASSET_SIZE,
        )

    @staticmethod
    def get_site_asset_upload_limit_bytes() -> int:
        return int(UploadService.get_site_asset_upload_limit_mb() * 1024 * 1024)

    @staticmethod
    def get_attachments_dir() -> str:
        settings_data = get_extension_settings("uploads")
        return UploadService._normalize_dir(settings_data.get("attachments_dir") or "attachments")

    @staticmethod
    def _normalize_dir(value: str) -> str:
        return str(value or "").strip("/\\") or "attachments"

    @staticmethod
    def _validate_attachment(file, max_size: int):
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise ValueError("不支持的文件格式")

        if file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValueError(f"文件大小超过限制（最大{max_size_mb}MB）")

    @staticmethod
    def _validate_site_asset(file, allowed_extensions, max_size: int):
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_extensions:
            raise ValueError(f"不支持的文件格式，仅支持: {', '.join(allowed_extensions)}")

        if file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValueError(f"文件大小超过限制（最大{max_size_mb}MB）")


def get_uploads_settings() -> dict:
    return get_extension_settings("uploads")


def get_upload_storage_backend():
    return get_storage_backend(get_uploads_settings())

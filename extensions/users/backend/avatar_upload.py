from __future__ import annotations

import os
import uuid
from io import BytesIO
from typing import Tuple

from django.core.files.uploadedfile import UploadedFile
from PIL import Image

from apps.core.extension_settings_service import get_extension_settings
from apps.core.file_service import FileUploadService
from apps.core.storage_service import get_storage_backend


ALLOWED_AVATAR_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
AVATAR_SIZES = {
    "small": (50, 50),
    "medium": (100, 100),
    "large": (200, 200),
}


class UserAvatarUploadService:
    MAX_AVATAR_SIZE = 2 * 1024 * 1024

    @staticmethod
    def upload_avatar(file: UploadedFile, user_id: int) -> Tuple[str, dict]:
        UserAvatarUploadService._validate_avatar(file, UserAvatarUploadService.get_avatar_upload_limit_bytes())

        ext = os.path.splitext(file.name)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        backend = get_storage_backend()

        original_bytes = FileUploadService.read_uploaded_file(file)
        avatars_dir = UserAvatarUploadService.get_avatars_dir()
        original_key = backend.build_user_key(avatars_dir, user_id, filename)
        original_url = backend.save_bytes(
            original_key,
            original_bytes,
            content_type=backend.guess_content_type(filename, file.content_type),
        )

        thumbnails = UserAvatarUploadService._generate_thumbnail_bytes(original_bytes, ext)
        thumbnail_urls = {}
        for size_name, thumb_bytes in thumbnails.items():
            thumb_filename = f"{os.path.splitext(filename)[0]}_{size_name}{ext}"
            thumb_key = backend.build_user_key(avatars_dir, user_id, thumb_filename)
            thumbnail_urls[size_name] = backend.save_bytes(
                thumb_key,
                thumb_bytes,
                content_type=backend.guess_content_type(thumb_filename, file.content_type),
            )

        return original_url, thumbnail_urls

    @staticmethod
    def delete_avatar(file_url: str) -> bool:
        backend = get_storage_backend()
        deleted = backend.delete(file_url)

        base, ext = os.path.splitext(file_url)
        for size_name in AVATAR_SIZES.keys():
            backend.delete(f"{base}_{size_name}{ext}")

        return deleted

    @staticmethod
    def _validate_avatar(file: UploadedFile, max_size: int):
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_AVATAR_EXTENSIONS:
            raise ValueError(f"不支持的图片格式，仅支持: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}")

        if file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValueError(f"文件大小超过限制（最大{max_size_mb}MB）")

        try:
            image = Image.open(file)
            image.verify()
        except Exception as exc:
            raise ValueError("无效的图片文件") from exc
        finally:
            if hasattr(file, "seek"):
                file.seek(0)

    @staticmethod
    def get_avatar_upload_limit_mb() -> int:
        settings_data = get_extension_settings("users")
        return FileUploadService._normalize_upload_size_mb(
            settings_data.get("avatar_max_size_mb"),
            UserAvatarUploadService.MAX_AVATAR_SIZE,
        )

    @staticmethod
    def get_avatar_upload_limit_bytes() -> int:
        return int(UserAvatarUploadService.get_avatar_upload_limit_mb() * 1024 * 1024)

    @staticmethod
    def get_avatars_dir() -> str:
        settings_data = get_extension_settings("users")
        return UserAvatarUploadService._normalize_dir(settings_data.get("avatars_dir") or "avatars")

    @staticmethod
    def _normalize_dir(value: str) -> str:
        return str(value or "").strip("/\\") or "avatars"

    @staticmethod
    def _generate_thumbnail_bytes(image_bytes: bytes, ext: str) -> dict:
        thumbnails = {}

        try:
            image = Image.open(BytesIO(image_bytes))
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            output_format = UserAvatarUploadService._image_output_format(ext)
            for size_name, (width, height) in AVATAR_SIZES.items():
                thumb = image.copy()
                thumb.thumbnail((width, height), Image.Resampling.LANCZOS)

                buffer = BytesIO()
                save_kwargs = {"format": output_format}
                if output_format in ("JPEG", "WEBP"):
                    save_kwargs.update({"quality": 85, "optimize": True})
                thumb.save(buffer, **save_kwargs)
                thumbnails[size_name] = buffer.getvalue()
        except Exception:
            return {}

        return thumbnails

    @staticmethod
    def _image_output_format(ext: str) -> str:
        if ext in (".jpg", ".jpeg"):
            return "JPEG"
        if ext == ".webp":
            return "WEBP"
        if ext == ".gif":
            return "GIF"
        return "PNG"

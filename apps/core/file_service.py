"""
文件上传功能业务逻辑层
"""
import hashlib

from django.core.files.uploadedfile import UploadedFile

from apps.core.storage_service import get_storage_backend


class FileUploadService:
    """文件上传服务"""

    MIN_UPLOAD_SIZE_MB = 1
    MAX_UPLOAD_SIZE_MB = 100

    @staticmethod
    def _normalize_upload_size_mb(value, default_bytes: int) -> int:
        default_mb = max(1, int(default_bytes / (1024 * 1024)))
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = default_mb
        return min(FileUploadService.MAX_UPLOAD_SIZE_MB, max(FileUploadService.MIN_UPLOAD_SIZE_MB, normalized))

    @staticmethod
    def read_uploaded_file(file: UploadedFile) -> bytes:
        if hasattr(file, 'seek'):
            file.seek(0)
        content = b''.join(file.chunks())
        if hasattr(file, 'seek'):
            file.seek(0)
        return content

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def delete_file(file_url: str) -> bool:
        backend = get_storage_backend()
        return backend.delete(file_url)

"""
运行时文件存储服务
"""
import json
import mimetypes
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx
from django.conf import settings

from apps.core.settings_service import ADVANCED_SETTINGS_DEFAULTS, get_setting_group


def get_runtime_storage_settings() -> dict:
    return get_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS)


class BaseStorageBackend:
    def __init__(self, config: dict):
        self.config = config
        self.attachments_dir = self._normalize_dir(config.get("storage_attachments_dir") or "attachments")
        self.avatars_dir = self._normalize_dir(config.get("storage_avatars_dir") or "avatars")

    def save_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        raise NotImplementedError

    def delete_key(self, key: str) -> bool:
        raise NotImplementedError

    def delete(self, file_url: str) -> bool:
        key = self.extract_key(file_url)
        if not key:
            return False
        return self.delete_key(key)

    def extract_key(self, file_url: str) -> Optional[str]:
        return None

    def build_user_key(self, category_dir: str, user_id: int, filename: str) -> str:
        return self.join_key(category_dir, str(user_id), filename)

    @staticmethod
    def join_key(*parts: str) -> str:
        cleaned = [str(part).strip("/") for part in parts if part not in (None, "")]
        return "/".join(cleaned)

    @staticmethod
    def guess_content_type(filename: str, provided: Optional[str] = None) -> str:
        if provided:
            return provided
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    @staticmethod
    def _normalize_dir(value: str) -> str:
        return str(value or "").strip("/\\") or ""

    @staticmethod
    def _normalize_public_base(value: str) -> str:
        base = str(value or "").strip()
        if not base:
            return ""
        return base if base.endswith("/") else f"{base}/"

    @staticmethod
    def _strip_public_base(file_url: str, public_base: str) -> Optional[str]:
        if not file_url or not public_base:
            return None

        normalized_base = BaseStorageBackend._normalize_public_base(public_base)
        if file_url.startswith(normalized_base):
            return file_url[len(normalized_base):].lstrip("/")

        parsed_file = urlsplit(file_url)
        parsed_base = urlsplit(normalized_base)
        base_path = parsed_base.path or "/"
        if not base_path.endswith("/"):
            base_path = f"{base_path}/"

        if parsed_base.scheme or parsed_base.netloc:
            if parsed_file.scheme == parsed_base.scheme and parsed_file.netloc == parsed_base.netloc:
                if parsed_file.path.startswith(base_path):
                    return parsed_file.path[len(base_path):].lstrip("/")
            return None

        candidate_path = parsed_file.path or file_url
        if candidate_path.startswith(base_path):
            return candidate_path[len(base_path):].lstrip("/")
        return None


class LocalStorageBackend(BaseStorageBackend):
    def __init__(self, config: dict):
        super().__init__(config)
        configured_path = str(config.get("storage_local_path") or getattr(settings, "MEDIA_ROOT", "media")).strip()
        root = Path(configured_path)
        self.root_path = root if root.is_absolute() else Path(settings.BASE_DIR) / root
        self.base_url = self._normalize_public_base(
            config.get("storage_local_base_url") or getattr(settings, "MEDIA_URL", "/media/")
        )

    def save_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        file_path = self.root_path.joinpath(*key.split("/"))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return f"{self.base_url}{key}"

    def delete_key(self, key: str) -> bool:
        file_path = self.root_path.joinpath(*key.split("/"))
        if not file_path.exists():
            return False
        file_path.unlink()
        return True

    def extract_key(self, file_url: str) -> Optional[str]:
        return self._strip_public_base(file_url, self.base_url)


class S3CompatibleStorageBackend(BaseStorageBackend):
    def __init__(self, config: dict, prefix: str):
        super().__init__(config)
        self.prefix_name = prefix
        self.bucket = str(config.get(f"storage_{prefix}_bucket") or "").strip()
        self.region = str(config.get(f"storage_{prefix}_region") or "").strip() if prefix == "s3" else ""
        self.endpoint = str(config.get(f"storage_{prefix}_endpoint") or "").strip()
        self.access_key_id = str(config.get(f"storage_{prefix}_access_key_id") or "").strip()
        self.secret_access_key = str(config.get(f"storage_{prefix}_secret_access_key") or "").strip()
        self.public_url = str(config.get(f"storage_{prefix}_public_url") or "").strip()
        self.object_prefix = str(config.get(f"storage_{prefix}_object_prefix") or "").strip("/ ")
        self.path_style = bool(config.get("storage_s3_path_style", False)) if prefix == "s3" else True
        self._client_instance = None

    def save_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        full_key = self._full_key(key)
        self._client().put_object(
            Bucket=self.bucket,
            Key=full_key,
            Body=content,
            ContentType=content_type or self.guess_content_type(key),
        )
        return self._public_url_for_key(full_key)

    def delete_key(self, key: str) -> bool:
        self._client().delete_object(Bucket=self.bucket, Key=self._full_key(key))
        return True

    def extract_key(self, file_url: str) -> Optional[str]:
        public_base = self._public_base_url()
        relative = self._strip_public_base(file_url, public_base)
        if not relative:
            return None

        if self.object_prefix and relative.startswith(f"{self.object_prefix}/"):
            return relative[len(self.object_prefix) + 1:]
        return relative

    def _full_key(self, key: str) -> str:
        return self.join_key(self.object_prefix, key)

    def _public_url_for_key(self, full_key: str) -> str:
        return f"{self._public_base_url()}{full_key}"

    def _public_base_url(self) -> str:
        if self.public_url:
            return self._normalize_public_base(self.public_url)

        if self.prefix_name == "r2":
            raise ValueError("Cloudflare R2 需要配置公共访问 URL 或 CDN 域名")

        if not self.bucket:
            raise ValueError("S3 Bucket 未配置")

        region = self.region or "us-east-1"
        if self.endpoint:
            endpoint = self.endpoint if self.endpoint.startswith(("http://", "https://")) else f"https://{self.endpoint}"
            parsed = urlsplit(endpoint)
            host = parsed.netloc or parsed.path
            base = f"https://{host}/{self.bucket}" if self.path_style else f"https://{self.bucket}.{host}"
            return self._normalize_public_base(base)

        host = "s3.amazonaws.com" if region == "us-east-1" else f"s3.{region}.amazonaws.com"
        base = f"https://{host}/{self.bucket}" if self.path_style else f"https://{self.bucket}.{host}"
        return self._normalize_public_base(base)

    def _client(self):
        if self._client_instance is not None:
            return self._client_instance

        if not self.bucket:
            raise ValueError("Bucket 未配置")
        if not self.access_key_id or not self.secret_access_key:
            raise ValueError("Access Key 未配置")

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ValueError("使用 S3 或 R2 存储需要安装 boto3") from exc

        self._client_instance = boto3.client(
            "s3",
            endpoint_url=self.endpoint or None,
            region_name=self.region or None,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(s3={"addressing_style": "path" if self.path_style else "virtual"}),
        )
        return self._client_instance


class AliyunOssStorageBackend(BaseStorageBackend):
    def __init__(self, config: dict):
        super().__init__(config)
        self.bucket = str(config.get("storage_oss_bucket") or "").strip()
        self.endpoint = str(config.get("storage_oss_endpoint") or "").strip()
        self.access_key_id = str(config.get("storage_oss_access_key_id") or "").strip()
        self.access_key_secret = str(config.get("storage_oss_access_key_secret") or "").strip()
        self.public_url = str(config.get("storage_oss_public_url") or "").strip()
        self.object_prefix = str(config.get("storage_oss_object_prefix") or "").strip("/ ")
        self._bucket_instance = None

    def save_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        full_key = self._full_key(key)
        headers = {"Content-Type": content_type or self.guess_content_type(key)}
        self._bucket().put_object(full_key, content, headers=headers)
        return self._public_url_for_key(full_key)

    def delete_key(self, key: str) -> bool:
        self._bucket().delete_object(self._full_key(key))
        return True

    def extract_key(self, file_url: str) -> Optional[str]:
        relative = self._strip_public_base(file_url, self._public_base_url())
        if not relative:
            return None
        if self.object_prefix and relative.startswith(f"{self.object_prefix}/"):
            return relative[len(self.object_prefix) + 1:]
        return relative

    def _full_key(self, key: str) -> str:
        return self.join_key(self.object_prefix, key)

    def _public_url_for_key(self, full_key: str) -> str:
        return f"{self._public_base_url()}{full_key}"

    def _public_base_url(self) -> str:
        if self.public_url:
            return self._normalize_public_base(self.public_url)
        if not self.bucket or not self.endpoint:
            raise ValueError("阿里云 OSS 需要配置 Bucket、Endpoint 和公共访问地址")
        endpoint_host = self.endpoint.replace("https://", "").replace("http://", "").strip("/")
        return self._normalize_public_base(f"https://{self.bucket}.{endpoint_host}")

    def _bucket(self):
        if self._bucket_instance is not None:
            return self._bucket_instance

        if not self.bucket or not self.endpoint:
            raise ValueError("Bucket 或 Endpoint 未配置")
        if not self.access_key_id or not self.access_key_secret:
            raise ValueError("Access Key 未配置")

        try:
            import oss2
        except ImportError as exc:
            raise ValueError("使用阿里云 OSS 需要安装 oss2") from exc

        endpoint = self.endpoint if self.endpoint.startswith(("http://", "https://")) else f"https://{self.endpoint}"
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self._bucket_instance = oss2.Bucket(auth, endpoint, self.bucket)
        return self._bucket_instance


class ImageBedStorageBackend(BaseStorageBackend):
    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = str(config.get("storage_imagebed_endpoint") or "").strip()
        self.method = str(config.get("storage_imagebed_method") or "POST").strip().upper()
        self.file_field = str(config.get("storage_imagebed_file_field") or "file").strip()
        self.headers_text = str(config.get("storage_imagebed_headers") or "{}").strip()
        self.form_data_text = str(config.get("storage_imagebed_form_data") or "{}").strip()
        self.url_path = str(config.get("storage_imagebed_url_path") or "data.url").strip()

    def save_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        if not self.endpoint:
            raise ValueError("图床上传地址未配置")

        headers = self._load_json_object(self.headers_text, "图床请求头")
        form_data = self._load_json_object(self.form_data_text, "图床附加参数")

        response = httpx.request(
            self.method,
            self.endpoint,
            headers=headers,
            data=form_data,
            files={
                self.file_field: (
                    Path(key).name,
                    content,
                    content_type or self.guess_content_type(key),
                )
            },
            timeout=30,
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ValueError("图床返回的不是合法 JSON") from exc

        file_url = self._extract_json_path(payload, self.url_path)
        if not file_url or not isinstance(file_url, str):
            raise ValueError("图床返回中未找到图片地址，请检查响应路径配置")
        return file_url

    def delete_key(self, key: str) -> bool:
        return False

    def delete(self, file_url: str) -> bool:
        return False

    @staticmethod
    def _load_json_object(raw_text: str, label: str) -> dict:
        if not raw_text:
            return {}
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} 不是合法 JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{label} 必须是 JSON 对象")
        return parsed

    @staticmethod
    def _extract_json_path(payload: Any, path: str) -> Any:
        current = payload
        for part in [item for item in path.split(".") if item]:
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError) as exc:
                    raise ValueError("图床响应路径无效") from exc
                continue
            if not isinstance(current, dict) or part not in current:
                raise ValueError("图床响应路径无效")
            current = current[part]
        return current


def get_storage_backend(config: Optional[dict] = None) -> BaseStorageBackend:
    runtime_config = config or get_runtime_storage_settings()
    driver = str(runtime_config.get("storage_driver") or "local").strip().lower()

    if driver not in {"local", "s3", "r2", "oss", "imagebed"}:
        from apps.core.extensions.system_runtime import resolve_runtime_filesystem_driver

        backend = resolve_runtime_filesystem_driver(driver, runtime_config)
        if backend is not None:
            return backend

    if driver == "local":
        return LocalStorageBackend(runtime_config)
    if driver == "s3":
        return S3CompatibleStorageBackend(runtime_config, "s3")
    if driver == "r2":
        return S3CompatibleStorageBackend(runtime_config, "r2")
    if driver == "oss":
        return AliyunOssStorageBackend(runtime_config)
    if driver == "imagebed":
        return ImageBedStorageBackend(runtime_config)

    raise ValueError("不支持的文件存储驱动")

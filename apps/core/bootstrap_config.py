from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_SITE_CONFIG_PATH = Path("instance") / "site.json"


def _env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_first(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip():
            return value.strip()
    return ""


def _normalize_frontend_url(value: str, scheme: str, domains: list[str]) -> str:
    raw = (value or "").strip()
    if raw:
        parsed = urlparse(raw if "://" in raw else f"{scheme}://{raw}")
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    if not domains:
        return ""

    host = domains[0]
    parsed = urlparse(host if "://" in host else f"{scheme}://{host}")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    return ""


@dataclass
class SiteBootstrapConfig:
    installed: bool = False
    source: str = "none"
    debug: bool = False
    secret_key: str = "django-insecure-change-this-in-production"
    jwt_secret_key: str = "jwt-secret-key-change-this"
    jwt_algorithm: str = "HS256"
    jwt_access_token_lifetime: int = 3600
    jwt_refresh_token_lifetime: int = 86400
    site_domains: list[str] = field(default_factory=list)
    site_scheme: str = "https"
    frontend_url: str = ""
    database_mode: str = "sqlite"
    sqlite_name: str = "db.sqlite3"
    db_engine: str = "django.db.backends.postgresql"
    db_name: str = "bias"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "localhost"
    db_port: str = "5432"
    use_redis: bool = False
    redis_host: str = "localhost"
    redis_port: str = "6379"
    redis_db: str = "0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    email_backend: str = "django.core.mail.backends.console.EmailBackend"
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_use_tls: bool = True
    email_host_user: str = ""
    email_host_password: str = ""
    default_from_email: str = "noreply@bias.local"
    media_url: str = "/media/"
    static_url: str = "/static/"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    def resolved_frontend_url(self) -> str:
        default_scheme = self.site_scheme or "https"
        return _normalize_frontend_url(self.frontend_url, default_scheme, self.site_domains)

    def resolved_allowed_hosts(self) -> list[str]:
        hosts = ["localhost", "127.0.0.1"]
        for entry in self.site_domains:
            parsed = urlparse(entry if "://" in entry else f"{self.site_scheme}://{entry}")
            if parsed.hostname and parsed.hostname not in hosts:
                hosts.append(parsed.hostname)

        frontend = self.resolved_frontend_url()
        if frontend:
            parsed = urlparse(frontend)
            if parsed.hostname and parsed.hostname not in hosts:
                hosts.append(parsed.hostname)

        return hosts

    def resolved_cors_origins(self) -> list[str]:
        origins = ["http://localhost:3000", "http://localhost:5173"]
        frontend = self.resolved_frontend_url()
        if frontend and frontend not in origins:
            origins.append(frontend)

        for entry in self.site_domains:
            parsed = urlparse(entry if "://" in entry else f"{self.site_scheme}://{entry}")
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
            if origin and origin not in origins:
                origins.append(origin)

        return origins

    def resolved_csrf_origins(self) -> list[str]:
        return list(self.resolved_cors_origins())


def get_site_config_path(base_dir: str | Path) -> Path:
    raw = os.getenv("BIAS_SITE_CONFIG")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else Path(base_dir) / path

    return Path(base_dir) / DEFAULT_SITE_CONFIG_PATH


def write_site_config(path: str | Path, config: SiteBootstrapConfig) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def read_site_config(path: str | Path) -> SiteBootstrapConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    config = SiteBootstrapConfig(**data)
    config.frontend_url = config.resolved_frontend_url()
    return config


def load_site_bootstrap(base_dir: str | Path) -> SiteBootstrapConfig:
    base_path = Path(base_dir)
    config_path = get_site_config_path(base_path)
    if config_path.exists():
        config = read_site_config(config_path)
        config.source = "file"
        config.installed = True
        return config

    if _is_test_process():
        return SiteBootstrapConfig(
            installed=True,
            source="test",
            debug=True,
            frontend_url="http://localhost:5173",
            site_scheme="http",
            database_mode="sqlite",
            use_redis=False,
        )

    env_config = _load_env_bootstrap()
    if env_config is not None:
        return env_config

    return SiteBootstrapConfig(installed=False, source="none", debug=False, database_mode="sqlite")


def _is_test_process() -> bool:
    argv = set(sys.argv)
    return "test" in argv or bool(os.getenv("PYTEST_CURRENT_TEST"))


def _load_env_bootstrap() -> SiteBootstrapConfig | None:
    db_name = _env_first("DB_NAME")
    db_user = _env_first("DB_USER")
    db_password = _env_first("DB_PASSWORD")

    if not (db_name and db_user and db_password):
        return None

    site_domains = _env_csv(_env_first("SITE_DOMAINS"))
    if any(domain.startswith("localhost") or domain.startswith("127.0.0.1") for domain in site_domains):
        default_scheme = "http"
    else:
        default_scheme = _env_first("SITE_SCHEME") or ("https" if site_domains else "http")

    config = SiteBootstrapConfig(
        installed=True,
        source="env",
        debug=_env_flag(os.getenv("DEBUG"), default=False),
        secret_key=_env_first("SECRET_KEY") or "django-insecure-change-this-in-production",
        jwt_secret_key=_env_first("JWT_SECRET_KEY") or _env_first("SECRET_KEY") or "jwt-secret-key-change-this",
        jwt_algorithm=_env_first("JWT_ALGORITHM") or "HS256",
        jwt_access_token_lifetime=int(_env_first("JWT_ACCESS_TOKEN_LIFETIME") or 3600),
        jwt_refresh_token_lifetime=int(_env_first("JWT_REFRESH_TOKEN_LIFETIME") or 86400),
        site_domains=site_domains,
        site_scheme=default_scheme,
        frontend_url=_env_first("FRONTEND_URL"),
        database_mode="postgres",
        sqlite_name="db.sqlite3",
        db_engine=_env_first("DB_ENGINE") or "django.db.backends.postgresql",
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        db_host=_env_first("DB_HOST") or "db",
        db_port=_env_first("DB_PORT") or "5432",
        use_redis=_env_flag(os.getenv("USE_REDIS"), default=bool(_env_first("REDIS_HOST"))),
        redis_host=_env_first("REDIS_HOST") or "redis",
        redis_port=_env_first("REDIS_PORT") or "6379",
        redis_db=_env_first("REDIS_DB") or "0",
        celery_broker_url=_env_first("CELERY_BROKER_URL"),
        celery_result_backend=_env_first("CELERY_RESULT_BACKEND"),
        email_backend=_env_first("EMAIL_BACKEND") or "django.core.mail.backends.console.EmailBackend",
        email_host=_env_first("EMAIL_HOST") or "smtp.gmail.com",
        email_port=int(_env_first("EMAIL_PORT") or 587),
        email_use_tls=_env_flag(os.getenv("EMAIL_USE_TLS"), default=True),
        email_host_user=_env_first("EMAIL_HOST_USER"),
        email_host_password=_env_first("EMAIL_HOST_PASSWORD"),
        default_from_email=_env_first("DEFAULT_FROM_EMAIL") or "noreply@bias.local",
        media_url=_env_first("MEDIA_URL") or "/media/",
        static_url=_env_first("STATIC_URL") or "/static/",
    )
    config.frontend_url = config.resolved_frontend_url()
    return config

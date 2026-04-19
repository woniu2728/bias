from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values


DEFAULT_SITE_CONFIG_PATH = Path("instance") / "site.json"
LEGACY_ENV_FILE = ".env"
LEGACY_ENV_MARKERS = {
    "DB_MODE",
    "SQLITE_NAME",
    "DB_ENGINE",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "FRONTEND_URL",
}


def _env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_env_file(path: Path) -> dict[str, str]:
    return {key: str(value) for key, value in dotenv_values(path).items() if value is not None}


def _looks_like_legacy_site_env(values: dict[str, str]) -> bool:
    return any(key in values for key in LEGACY_ENV_MARKERS)


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

    legacy = _load_legacy_env_bootstrap(base_path)
    if legacy is not None:
        legacy.source = "env"
        legacy.installed = True
        return legacy

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

    return SiteBootstrapConfig(installed=False, source="none", debug=False, database_mode="sqlite")


def _load_legacy_env_bootstrap(base_path: Path) -> SiteBootstrapConfig | None:
    env_values: dict[str, str] = {}
    env_path = os.getenv("BIAS_ENV_FILE")
    if env_path:
        path = Path(env_path)
        if not path.is_absolute():
            path = base_path / path
        if path.exists():
            env_values.update(_read_env_file(path))

    default_env_path = base_path / LEGACY_ENV_FILE
    if not env_values and default_env_path.exists():
        default_values = _read_env_file(default_env_path)
        if _looks_like_legacy_site_env(default_values):
            env_values.update(default_values)

    if not env_values:
        return None

    config = SiteBootstrapConfig(
        installed=True,
        debug=_env_flag(env_values.get("DEBUG"), default=True),
        secret_key=env_values.get("SECRET_KEY") or SiteBootstrapConfig.secret_key,
        jwt_secret_key=env_values.get("JWT_SECRET_KEY") or SiteBootstrapConfig.jwt_secret_key,
        jwt_algorithm=env_values.get("JWT_ALGORITHM") or SiteBootstrapConfig.jwt_algorithm,
        jwt_access_token_lifetime=int(env_values.get("JWT_ACCESS_TOKEN_LIFETIME") or 3600),
        jwt_refresh_token_lifetime=int(env_values.get("JWT_REFRESH_TOKEN_LIFETIME") or 86400),
        site_domains=_env_csv(env_values.get("SITE_DOMAINS")),
        site_scheme=(env_values.get("SITE_SCHEME") or "https").strip() or "https",
        frontend_url=env_values.get("FRONTEND_URL") or "",
        database_mode=(env_values.get("DB_MODE") or "sqlite").strip().lower(),
        sqlite_name=env_values.get("SQLITE_NAME") or "db.sqlite3",
        db_engine=env_values.get("DB_ENGINE") or "django.db.backends.postgresql",
        db_name=env_values.get("DB_NAME") or "bias",
        db_user=env_values.get("DB_USER") or "postgres",
        db_password=env_values.get("DB_PASSWORD") or "postgres",
        db_host=env_values.get("DB_HOST") or "localhost",
        db_port=env_values.get("DB_PORT") or "5432",
        use_redis=_env_flag(env_values.get("USE_REDIS"), default=False),
        redis_host=env_values.get("REDIS_HOST") or "localhost",
        redis_port=env_values.get("REDIS_PORT") or "6379",
        redis_db=env_values.get("REDIS_DB") or "0",
        celery_broker_url=env_values.get("CELERY_BROKER_URL") or "",
        celery_result_backend=env_values.get("CELERY_RESULT_BACKEND") or "",
        email_backend=env_values.get("EMAIL_BACKEND") or "django.core.mail.backends.console.EmailBackend",
        email_host=env_values.get("EMAIL_HOST") or "smtp.gmail.com",
        email_port=int(env_values.get("EMAIL_PORT") or 587),
        email_use_tls=_env_flag(env_values.get("EMAIL_USE_TLS"), default=True),
        email_host_user=env_values.get("EMAIL_HOST_USER") or "",
        email_host_password=env_values.get("EMAIL_HOST_PASSWORD") or "",
        default_from_email=env_values.get("DEFAULT_FROM_EMAIL") or "noreply@bias.local",
        media_url=env_values.get("MEDIA_URL") or "/media/",
        static_url=env_values.get("STATIC_URL") or "/static/",
    )
    config.frontend_url = config.resolved_frontend_url()
    return config


def _is_test_process() -> bool:
    argv = set(sys.argv)
    return "test" in argv or bool(os.getenv("PYTEST_CURRENT_TEST"))

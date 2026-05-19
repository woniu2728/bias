from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.core.checks import Critical, Tags, Warning, register

from apps.core.bootstrap_config import _is_test_process
from apps.core.queue_service import QueueService
from apps.core.settings_service import get_advanced_settings


MIN_HS256_KEY_LENGTH = 32
KNOWN_PLACEHOLDER_SECRETS = {
    "django-insecure-change-this-in-production",
    "jwt-secret-key-change-this",
}
NETWORK_PROBE_TIMEOUT_SECONDS = 0.3
PRODUCTION_RUNTIME_CHECK_TAG = "bias_runtime"


def detect_database_label() -> str:
    config = settings.DATABASES.get("default", {})
    engine = (config.get("ENGINE") or "").lower()
    if "sqlite" in engine:
        filename = Path(str(config.get("NAME") or "db.sqlite3")).name
        return f"SQLite ({filename})"
    if "postgresql" in engine:
        return f"PostgreSQL ({config.get('NAME') or '-'} @ {config.get('HOST') or 'localhost'})"
    if "mysql" in engine:
        return f"MySQL ({config.get('NAME') or '-'})"
    return engine or "未知"


def detect_cache_driver() -> str:
    backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    if "django_redis" in backend or "redis" in backend:
        return "Redis"
    if "locmem" in backend:
        return "内存"
    if "filebased" in backend:
        return "文件"
    if "database" in backend:
        return "数据库"
    return backend or "未知"


def detect_realtime_driver() -> str:
    backend = (settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND") or "").lower()
    if "channels_redis" in backend or "redis" in backend:
        return "Redis"
    if "inmemory" in backend:
        return "In-memory"
    return backend or "未知"


def detect_queue_driver_label(queue_enabled: bool, queue_driver: str) -> str:
    if not queue_enabled:
        return "同步执行"
    if queue_driver == "redis":
        return "Redis"
    return queue_driver or "未知"


def is_redis_enabled(queue_enabled: bool = False, queue_driver: str = "") -> bool:
    cache_backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    channel_backend = (settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND") or "").lower()
    broker = getattr(settings, "CELERY_BROKER_URL", "").lower()

    cache_uses_redis = "redis" in cache_backend
    realtime_uses_redis = "redis" in channel_backend
    queue_uses_redis = bool(queue_enabled and queue_driver == "redis" and "redis" in broker)

    return cache_uses_redis or realtime_uses_redis or queue_uses_redis


def _probe_cache_connection() -> dict[str, Any]:
    backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    if "django_redis" not in backend and "redis" not in backend:
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前默认缓存未使用 Redis。",
        }

    try:
        cache.set("admin.runtime.cache_probe", "ok", timeout=5)
        cache.get("admin.runtime.cache_probe")
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "unavailable",
            "label": "连接失败",
            "message": str(exc) or "无法访问缓存后端。",
        }

    return {
        "enabled": True,
        "available": True,
        "status": "available",
        "label": "可用",
        "message": "缓存后端可正常读写。",
    }


def _probe_tcp_endpoint(host: str | None, port: int | None, *, label: str) -> dict[str, Any]:
    normalized_host = str(host or "").strip()
    normalized_port = int(port or 0)
    if not normalized_host or normalized_port <= 0:
        return {
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": f"{label} 缺少主机或端口配置。",
        }

    try:
        with socket.create_connection((normalized_host, normalized_port), timeout=NETWORK_PROBE_TIMEOUT_SECONDS):
            return {
                "available": True,
                "status": "available",
                "label": "可达",
                "message": f"{label} 主机 {normalized_host}:{normalized_port} 可连通。",
            }
    except OSError as exc:
        return {
            "available": False,
            "status": "unreachable",
            "label": "不可达",
            "message": f"{label} 主机 {normalized_host}:{normalized_port} 无法连通：{exc}",
        }


def _probe_redis_ping(host: str | None, port: int | None, *, label: str) -> dict[str, Any]:
    normalized_host = str(host or "").strip()
    normalized_port = int(port or 0)
    if not normalized_host or normalized_port <= 0:
        return {
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": f"{label} 缺少主机或端口配置。",
        }

    try:
        with socket.create_connection((normalized_host, normalized_port), timeout=NETWORK_PROBE_TIMEOUT_SECONDS) as connection:
            connection.settimeout(NETWORK_PROBE_TIMEOUT_SECONDS)
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = connection.recv(64)
    except OSError as exc:
        return {
            "available": False,
            "status": "unreachable",
            "label": "不可达",
            "message": f"{label} 主机 {normalized_host}:{normalized_port} 无法连通：{exc}",
        }

    if response.startswith(b"+PONG"):
        return {
            "available": True,
            "status": "available",
            "label": "可用",
            "message": f"{label} 返回 Redis PONG，服务可用。",
        }

    return {
        "available": False,
        "status": "protocol-error",
        "label": "协议异常",
        "message": f"{label} 已建立连接，但未返回 Redis PONG。",
    }


def _probe_realtime_connection() -> dict[str, Any]:
    channel_config = settings.CHANNEL_LAYERS.get("default", {})
    backend = (channel_config.get("BACKEND") or "").lower()
    if "channels_redis" not in backend and "redis" not in backend:
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前实时层未使用 Redis Channel Layer。",
        }

    hosts = channel_config.get("CONFIG", {}).get("hosts") or []
    if not hosts:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "Redis Channel Layer 缺少 hosts 配置。",
        }

    first_host = hosts[0]
    if isinstance(first_host, (list, tuple)):
        host = first_host[0] if len(first_host) > 0 else None
        port = first_host[1] if len(first_host) > 1 else 6379
    elif isinstance(first_host, str):
        parsed = urlparse(first_host if "://" in first_host else f"redis://{first_host}")
        host = parsed.hostname
        port = parsed.port or 6379
    else:
        host = None
        port = None

    connectivity = _probe_redis_ping(host, port, label="Redis Channel Layer")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


def _probe_queue_broker_connection(queue_enabled: bool, queue_driver: str) -> dict[str, Any]:
    normalized_driver = str(queue_driver or "").strip().lower()
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
    if not queue_enabled or normalized_driver != "redis":
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前未启用 Redis 队列 broker。",
        }

    if not broker_url:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "队列已启用，但 CELERY_BROKER_URL 为空。",
        }

    parsed = urlparse(broker_url)
    if "redis" not in (parsed.scheme or "").lower():
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "驱动不匹配",
            "message": "队列驱动为 Redis，但 broker URL 不是 Redis 协议。",
        }

    if not parsed.hostname:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "Redis broker 缺少主机配置。",
        }

    connectivity = _probe_redis_ping(parsed.hostname, parsed.port or 6379, label="Redis broker")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


def _normalize_secret_value(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = value.lower()
    return normalized in KNOWN_PLACEHOLDER_SECRETS or "change-this" in normalized


def _jwt_key_length_requirement(algorithm: str) -> int:
    normalized = str(algorithm or "").strip().upper()
    if normalized.startswith("HS"):
        return MIN_HS256_KEY_LENGTH
    return 0


def build_auth_secret_risks() -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    secret_key = _normalize_secret_value(settings.SECRET_KEY)
    jwt_algorithm = str(settings.NINJA_JWT.get("ALGORITHM") or "").strip().upper()
    jwt_signing_key = _normalize_secret_value(settings.NINJA_JWT.get("SIGNING_KEY") or settings.SECRET_KEY)
    jwt_required_length = _jwt_key_length_requirement(jwt_algorithm)

    if _looks_like_placeholder_secret(secret_key):
        risks.append(
            {
                "code": "django-secret-placeholder",
                "level": "danger",
                "title": "Django SECRET_KEY 仍为默认占位值",
                "message": "当前 SECRET_KEY 仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if _looks_like_placeholder_secret(jwt_signing_key):
        risks.append(
            {
                "code": "jwt-secret-placeholder",
                "level": "danger",
                "title": "JWT 签名密钥仍为默认占位值",
                "message": "当前 JWT 签名密钥仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if jwt_required_length and len(jwt_signing_key) < jwt_required_length:
        risks.append(
            {
                "code": "jwt-secret-too-short",
                "level": "danger",
                "title": "JWT 签名密钥长度不足",
                "message": f"当前 {jwt_algorithm or 'JWT'} 签名密钥长度小于 {jwt_required_length} 字节，存在被弱密钥攻击的风险。",
            }
        )

    return risks


def build_auth_secret_status() -> dict[str, Any]:
    risks = build_auth_secret_risks()
    if risks:
        highest_level = "danger" if any(item.get("level") == "danger" for item in risks) else "warning"
        return {
            "status": highest_level,
            "label": "存在风险",
            "message": "；".join(item.get("title") or "" for item in risks if item.get("title")),
        }

    return {
        "status": "healthy",
        "label": "健康",
        "message": "Django 与 JWT 密钥未发现默认占位值或长度不足问题。",
    }


def build_runtime_risks(
    *,
    debug_mode: bool,
    database_label: str,
    cache_driver: str,
    realtime_driver: str,
    queue_enabled: bool,
    queue_driver: str,
    queue_worker_status: dict[str, Any],
    redis_enabled: bool,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    normalized_database_label = str(database_label or "").lower()
    normalized_cache_driver = str(cache_driver or "").lower()
    normalized_realtime_driver = str(realtime_driver or "").lower()
    normalized_queue_driver = str(queue_driver or "").lower()

    if debug_mode:
        risks.append(
            {
                "code": "debug-enabled",
                "level": "warning",
                "title": "DEBUG 模式仍处于开启状态",
                "message": "生产环境应关闭 DEBUG，避免泄露调试信息并影响缓存与异常处理行为。",
            }
        )

    is_production_like = "postgresql" in normalized_database_label
    if is_production_like and not redis_enabled:
        risks.append(
            {
                "code": "redis-disabled-production",
                "level": "danger",
                "title": "生产形态下未启用 Redis",
                "message": "当前使用 PostgreSQL，但缓存、实时层与队列未形成 Redis 底座，不符合路线图中的生产约束要求。",
            }
        )

    if is_production_like and "内存" in cache_driver:
        risks.append(
            {
                "code": "locmem-cache-production",
                "level": "danger",
                "title": "生产形态下仍在使用内存缓存",
                "message": "LocMemCache 只适合开发环境，多进程部署下会导致缓存割裂与状态不一致。",
            }
        )

    if queue_enabled and normalized_queue_driver == "redis" and not queue_worker_status.get("available"):
        risks.append(
            {
                "code": "queue-worker-unavailable",
                "level": "danger",
                "title": "队列已启用但没有可用 worker",
                "message": queue_worker_status.get("message") or "当前队列会持续回退到同步执行，后台异步任务无法稳定处理。",
            }
        )

    if cache_connection.get("enabled") and cache_connection.get("available") is False:
        risks.append(
            {
                "code": "cache-backend-unavailable",
                "level": "danger",
                "title": "缓存后端不可用",
                "message": cache_connection.get("message") or "当前缓存后端无法正常访问。",
            }
        )

    if realtime_connection.get("enabled") and realtime_connection.get("available") is False:
        risks.append(
            {
                "code": "realtime-backend-unavailable",
                "level": "warning",
                "title": "实时层配置不完整",
                "message": realtime_connection.get("message") or "当前实时层无法确认 Redis Channel Layer 可用。",
            }
        )

    if queue_broker_connection.get("enabled") and queue_broker_connection.get("available") is False:
        risks.append(
            {
                "code": "queue-broker-unavailable",
                "level": "danger",
                "title": "队列 broker 不可用",
                "message": queue_broker_connection.get("message") or "当前队列 broker 无法使用。",
            }
        )

    if queue_enabled and normalized_queue_driver != "redis":
        risks.append(
            {
                "code": "queue-driver-nonredis",
                "level": "warning",
                "title": "队列已启用但未使用 Redis 驱动",
                "message": "当前 worker 健康检测与稳定异步链路主要围绕 Redis/Celery 设计，其他驱动暂未形成完整生产闭环。",
            }
        )

    if is_production_like and normalized_realtime_driver == "in-memory":
        risks.append(
            {
                "code": "realtime-inmemory-production",
                "level": "warning",
                "title": "实时层仍使用内存通道",
                "message": "In-memory Channel Layer 不适合多实例部署，WebSocket 消息无法跨进程共享。",
            }
        )

    if is_production_like and normalized_cache_driver not in {"redis", "memcached"}:
        risks.append(
            {
                "code": "cache-driver-nonshared",
                "level": "warning",
                "title": "缓存驱动不是共享缓存",
                "message": "当前缓存驱动缺少跨实例共享能力，生产环境下容易出现配置和统计状态不一致。",
            }
        )

    if is_production_like:
        frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
        if not frontend_url:
            risks.append(
                {
                    "code": "frontend-url-missing-production",
                    "level": "danger",
                    "title": "生产形态下缺少 FRONTEND_URL",
                    "message": "邮件链接、验证链接和前台跳转依赖 FRONTEND_URL，生产环境必须提供有效前端地址。",
                }
            )

        email_backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").strip().lower()
        if "console" in email_backend or "locmem" in email_backend:
            risks.append(
                {
                    "code": "email-backend-development-production",
                    "level": "danger",
                    "title": "生产形态下仍在使用开发型邮件后端",
                    "message": "当前邮件后端仍是 console/locmem，生产环境会导致邮件无法真正发送。",
                }
            )

    risks.extend(build_auth_secret_risks())
    return risks


def build_runtime_dependency_checks(
    *,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
    queue_worker_status: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "key": "cache",
            "label": "缓存后端",
            "status": cache_connection.get("status") or "unknown",
            "status_label": cache_connection.get("label") or "未知",
            "available": cache_connection.get("available"),
            "message": cache_connection.get("message") or "",
            "recommended_action": (
                "确认 Redis 缓存服务在线，并检查 Django `CACHES` 配置、网络与认证信息。"
                if cache_connection.get("enabled") and cache_connection.get("available") is False
                else ""
            ),
        },
        {
            "key": "realtime",
            "label": "实时层",
            "status": realtime_connection.get("status") or "unknown",
            "status_label": realtime_connection.get("label") or "未知",
            "available": realtime_connection.get("available"),
            "message": realtime_connection.get("message") or "",
            "recommended_action": (
                "补全 `CHANNEL_LAYERS.default.CONFIG.hosts`，并在多实例部署前切换到 Redis Channel Layer。"
                if realtime_connection.get("enabled") and realtime_connection.get("available") is False
                else ""
            ),
        },
        {
            "key": "queue-broker",
            "label": "队列 Broker",
            "status": queue_broker_connection.get("status") or "unknown",
            "status_label": queue_broker_connection.get("label") or "未知",
            "available": queue_broker_connection.get("available"),
            "message": queue_broker_connection.get("message") or "",
            "recommended_action": (
                "确认 `CELERY_BROKER_URL` 使用 Redis 协议且主机配置完整，再重新加载 worker。"
                if queue_broker_connection.get("enabled") and queue_broker_connection.get("available") is False
                else ""
            ),
        },
        {
            "key": "queue-worker",
            "label": "队列 Worker",
            "status": queue_worker_status.get("status") or "unknown",
            "status_label": queue_worker_status.get("label") or "未知",
            "available": queue_worker_status.get("available"),
            "message": queue_worker_status.get("message") or "",
            "recommended_action": (
                "启动 Celery worker 并确认其能连接到当前 Redis broker。"
                if queue_worker_status.get("status") not in {QueueService.STATUS_DISABLED, QueueService.STATUS_SYNC}
                and not queue_worker_status.get("available")
                else ""
            ),
        },
    ]


def collect_runtime_readiness() -> dict[str, Any]:
    advanced_settings = get_advanced_settings()
    queue_driver = str(advanced_settings.get("queue_driver") or "sync").strip().lower()
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    database_label = detect_database_label()
    cache_driver = detect_cache_driver()
    realtime_driver = detect_realtime_driver()
    redis_enabled = is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver)
    cache_connection = _probe_cache_connection()
    realtime_connection = _probe_realtime_connection()
    queue_broker_connection = _probe_queue_broker_connection(queue_enabled, queue_driver)
    runtime_risks = build_runtime_risks(
        debug_mode=settings.DEBUG,
        database_label=database_label,
        cache_driver=cache_driver,
        realtime_driver=realtime_driver,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        queue_worker_status=queue_worker_status,
        redis_enabled=redis_enabled,
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
    )
    runtime_dependency_checks = build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )
    auth_secret_status = build_auth_secret_status()
    return {
        "advanced_settings": advanced_settings,
        "queue_driver": queue_driver,
        "queue_enabled": queue_enabled,
        "queue_worker_status": queue_worker_status,
        "database_label": database_label,
        "cache_driver": cache_driver,
        "realtime_driver": realtime_driver,
        "redis_enabled": redis_enabled,
        "cache_connection": cache_connection,
        "realtime_connection": realtime_connection,
        "queue_broker_connection": queue_broker_connection,
        "runtime_risks": runtime_risks,
        "runtime_dependency_checks": runtime_dependency_checks,
        "auth_secret_status": auth_secret_status,
    }


def is_production_runtime() -> bool:
    bootstrap = getattr(settings, "BOOTSTRAP", None)
    return not settings.DEBUG and bool(getattr(bootstrap, "installed", False)) and not _is_test_process()


def build_runtime_check_messages(**kwargs: Any) -> list[Any]:
    readiness = kwargs or collect_runtime_readiness()
    messages: list[Any] = []

    for risk in readiness["runtime_risks"]:
        text = f"{risk['title']}：{risk['message']}"
        hint = ""
        for dependency in readiness["runtime_dependency_checks"]:
            if dependency.get("message") and dependency["key"] in risk["code"]:
                hint = dependency.get("recommended_action") or ""
                break

        check_id = f"bias.{risk['code']}"
        if risk.get("level") == "danger":
            messages.append(Critical(text, hint=hint, id=check_id))
        else:
            messages.append(Warning(text, hint=hint, id=check_id))

    return messages


@register(Tags.security, PRODUCTION_RUNTIME_CHECK_TAG)
def check_production_runtime_configuration(app_configs, **kwargs):
    if not is_production_runtime():
        return []
    return build_runtime_check_messages()

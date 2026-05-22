from typing import Any
from urllib.parse import urlparse


MIN_HS256_KEY_LENGTH = 32
KNOWN_PLACEHOLDER_SECRETS = {
    "django-insecure-change-this-in-production",
    "jwt-secret-key-change-this",
}


def probe_cache_connection(*, settings_obj, cache_backend) -> dict[str, Any]:
    backend = (settings_obj.CACHES.get("default", {}).get("BACKEND") or "").lower()
    if "django_redis" not in backend and "redis" not in backend:
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前默认缓存未使用 Redis。",
        }

    try:
        cache_backend.set("admin.runtime.cache_probe", "ok", timeout=5)
        cache_backend.get("admin.runtime.cache_probe")
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


def probe_realtime_connection(*, settings_obj, redis_probe) -> dict[str, Any]:
    channel_config = settings_obj.CHANNEL_LAYERS.get("default", {})
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

    connectivity = redis_probe(host, port, label="Redis Channel Layer")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


def probe_queue_broker_connection(
    *,
    settings_obj,
    queue_enabled: bool,
    queue_driver: str,
    redis_probe,
) -> dict[str, Any]:
    normalized_driver = str(queue_driver or "").strip().lower()
    broker_url = str(getattr(settings_obj, "CELERY_BROKER_URL", "") or "").strip()
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

    connectivity = redis_probe(parsed.hostname, parsed.port or 6379, label="Redis broker")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


def normalize_secret_value(value: Any) -> str:
    return str(value or "").strip()


def looks_like_placeholder_secret(value: str) -> bool:
    return value.lower() in KNOWN_PLACEHOLDER_SECRETS


def jwt_key_length_requirement(algorithm: str) -> int:
    normalized = str(algorithm or "").strip().upper()
    if normalized.startswith("HS"):
        return MIN_HS256_KEY_LENGTH
    return 0


def build_auth_secret_risks(
    *,
    secret_key: str,
    jwt_algorithm: str,
    jwt_signing_key: str,
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    jwt_required_length = jwt_key_length_requirement(jwt_algorithm)

    if looks_like_placeholder_secret(secret_key):
        risks.append(
            {
                "code": "django-secret-placeholder",
                "level": "danger",
                "title": "Django SECRET_KEY 仍为默认占位值",
                "message": "当前 SECRET_KEY 仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if looks_like_placeholder_secret(jwt_signing_key):
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


def build_auth_secret_status(*, risks: list[dict[str, Any]]) -> dict[str, Any]:
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
    auth_secret_risks: list[dict[str, Any]],
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

    risks.extend(auth_secret_risks)
    return risks


def validate_advanced_runtime_settings(
    payload: dict[str, Any],
    *,
    database_label: str,
    realtime_driver: str,
) -> list[str]:
    cache_driver = str(payload.get("cache_driver") or "").strip().lower()
    queue_driver = str(payload.get("queue_driver") or "").strip().lower()
    queue_enabled = bool(payload.get("queue_enabled", False))
    errors: list[str] = []

    is_postgres = "postgresql" in database_label.lower()
    normalized_realtime_driver = realtime_driver.lower()

    if is_postgres and cache_driver == "file":
        errors.append("PostgreSQL 生产形态下不允许将缓存驱动保存为文件缓存，请改用 Redis 或 Memcached。")

    if is_postgres and cache_driver == "内存":
        errors.append("PostgreSQL 生产形态下不允许继续使用内存缓存。")

    if queue_enabled and queue_driver != "redis":
        errors.append("启用队列处理时，当前仅允许使用 Redis 队列驱动。")

    if is_postgres and normalized_realtime_driver == "in-memory" and queue_enabled:
        errors.append("当前实时层仍是 In-memory，生产形态下启用队列前应先切换到 Redis Channel Layer。")

    return errors

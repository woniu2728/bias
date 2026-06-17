from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.core.cache import cache


class AuthRateLimitExceeded(Exception):
    pass


@dataclass(frozen=True)
class AuthRateLimitPolicy:
    limit: int
    window_seconds: int


POLICIES = {
    "login": AuthRateLimitPolicy(limit=5, window_seconds=15 * 60),
    "register": AuthRateLimitPolicy(limit=5, window_seconds=60 * 60),
    "forgot_password": AuthRateLimitPolicy(limit=5, window_seconds=60 * 60),
}


def check_auth_rate_limit(action: str, request, identifier: str = "") -> None:
    policy = POLICIES[action]
    for key in _rate_limit_keys(action, request, identifier):
        if int(cache.get(key) or 0) >= policy.limit:
            raise AuthRateLimitExceeded("请求过于频繁，请稍后再试")


def record_auth_rate_limit_failure(action: str, request, identifier: str = "") -> None:
    policy = POLICIES[action]
    for key in _rate_limit_keys(action, request, identifier):
        try:
            cache.add(key, 0, timeout=policy.window_seconds)
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=policy.window_seconds)


def clear_auth_rate_limit(action: str, request, identifier: str = "", *, dimensions: str = "all") -> None:
    """清除限流计数。

    dimensions: "all" — 清空所有维度（IP + ID）；"id" — 仅清空 ID 维度。
    登录成功应使用 dimensions="id" 避免清空共享 IP 的其他失败者计数。
    """
    keys = _ip_rate_limit_key(action, request, identifier, dimensions=dimensions)
    cache.delete_many(keys)


def _rate_limit_keys(action: str, request, identifier: str = "") -> list[str]:
    return _ip_rate_limit_key(action, request, identifier, dimensions="all")


def _ip_rate_limit_key(action: str, request, identifier: str = "", *, dimensions: str = "all") -> list[str]:
    ip = _client_ip(request)
    normalized_identifier = str(identifier or "").strip().lower()
    keys = []
    if dimensions in ("all", "ip"):
        keys.append(f"auth-rate-limit:{action}:ip:{_digest(ip)}")
    if normalized_identifier and dimensions != "ip":
        keys.append(f"auth-rate-limit:{action}:id:{_digest(normalized_identifier)}")
    return keys


def _client_ip(request) -> str:
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0].strip()
    return forwarded or str(request.META.get("REMOTE_ADDR") or "unknown")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

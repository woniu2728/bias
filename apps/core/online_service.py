from __future__ import annotations

import time
from typing import Dict, List

from django.conf import settings
from django.core.cache import cache

from apps.users.models import User

try:
    from django_redis import get_redis_connection
except Exception:  # pragma: no cover - optional dependency in local fallback mode
    get_redis_connection = None


class OnlineUserService:
    ONLINE_USERS_KEY = "bias:online_users"
    ONLINE_USER_COUNTS_KEY = "bias:online_user_counts"
    FALLBACK_CACHE_KEY = "bias:online_users:fallback"
    ONLINE_TTL_SECONDS = 90

    @staticmethod
    def mark_user_online(user_id: int) -> bool:
        connection = OnlineUserService._get_redis_connection()
        if connection is not None:
            return OnlineUserService._mark_user_online_redis(connection, user_id)
        return OnlineUserService._mark_user_online_fallback(user_id)

    @staticmethod
    def touch_user_online(user_id: int) -> bool:
        connection = OnlineUserService._get_redis_connection()
        if connection is not None:
            return OnlineUserService._touch_user_online_redis(connection, user_id)
        return OnlineUserService._touch_user_online_fallback(user_id)

    @staticmethod
    def mark_user_offline(user_id: int) -> bool:
        connection = OnlineUserService._get_redis_connection()
        if connection is not None:
            return OnlineUserService._mark_user_offline_redis(connection, user_id)
        return OnlineUserService._mark_user_offline_fallback(user_id)

    @staticmethod
    def get_online_users(limit: int = 50) -> List[dict]:
        user_ids = OnlineUserService.get_online_user_ids(limit=limit)
        if not user_ids:
            return []

        users = User.objects.filter(id__in=user_ids, is_active=True).only(
            "id",
            "username",
            "display_name",
            "avatar_url",
        )
        users_by_id = {user.id: user for user in users}

        return [
            {
                "id": users_by_id[user_id].id,
                "username": users_by_id[user_id].username,
                "display_name": users_by_id[user_id].display_name,
                "avatar_url": users_by_id[user_id].avatar_url,
            }
            for user_id in user_ids
            if user_id in users_by_id
        ]

    @staticmethod
    def get_online_user_ids(limit: int = 50) -> List[int]:
        connection = OnlineUserService._get_redis_connection()
        if connection is not None:
            return OnlineUserService._get_online_user_ids_redis(connection, limit)
        return OnlineUserService._get_online_user_ids_fallback(limit)

    @staticmethod
    def is_user_online(user_id: int) -> bool:
        return user_id in set(OnlineUserService.get_online_user_ids(limit=5000))

    @staticmethod
    def _get_redis_connection():
        backend = settings.CACHES.get("default", {}).get("BACKEND", "")
        if "django_redis" not in backend or get_redis_connection is None:
            return None

        try:
            return get_redis_connection("default")
        except Exception:
            return None

    @staticmethod
    def _mark_user_online_redis(connection, user_id: int) -> bool:
        OnlineUserService._cleanup_expired_redis(connection)
        key = str(user_id)
        now = OnlineUserService._now_ts()
        count = int(connection.hincrby(OnlineUserService.ONLINE_USER_COUNTS_KEY, key, 1))
        connection.zadd(OnlineUserService.ONLINE_USERS_KEY, {key: now + OnlineUserService.ONLINE_TTL_SECONDS})
        return count == 1

    @staticmethod
    def _touch_user_online_redis(connection, user_id: int) -> bool:
        OnlineUserService._cleanup_expired_redis(connection)
        key = str(user_id)
        if not connection.hexists(OnlineUserService.ONLINE_USER_COUNTS_KEY, key):
            return False

        connection.zadd(
            OnlineUserService.ONLINE_USERS_KEY,
            {key: OnlineUserService._now_ts() + OnlineUserService.ONLINE_TTL_SECONDS},
        )
        return True

    @staticmethod
    def _mark_user_offline_redis(connection, user_id: int) -> bool:
        OnlineUserService._cleanup_expired_redis(connection)
        key = str(user_id)
        raw_count = connection.hget(OnlineUserService.ONLINE_USER_COUNTS_KEY, key)
        count = int(raw_count or 0)
        if count <= 0:
            return False
        if count == 1:
            connection.hdel(OnlineUserService.ONLINE_USER_COUNTS_KEY, key)
            connection.zrem(OnlineUserService.ONLINE_USERS_KEY, key)
            return True

        connection.hincrby(OnlineUserService.ONLINE_USER_COUNTS_KEY, key, -1)
        connection.zadd(
            OnlineUserService.ONLINE_USERS_KEY,
            {key: OnlineUserService._now_ts() + OnlineUserService.ONLINE_TTL_SECONDS},
        )
        return False

    @staticmethod
    def _get_online_user_ids_redis(connection, limit: int) -> List[int]:
        OnlineUserService._cleanup_expired_redis(connection)
        raw_ids = connection.zrevrange(OnlineUserService.ONLINE_USERS_KEY, 0, max(limit - 1, 0))
        return [int(user_id) for user_id in raw_ids]

    @staticmethod
    def _cleanup_expired_redis(connection) -> None:
        now = OnlineUserService._now_ts()
        expired_user_ids = connection.zrangebyscore(OnlineUserService.ONLINE_USERS_KEY, "-inf", now)
        if expired_user_ids:
            connection.zremrangebyscore(OnlineUserService.ONLINE_USERS_KEY, "-inf", now)
            connection.hdel(OnlineUserService.ONLINE_USER_COUNTS_KEY, *expired_user_ids)

    @staticmethod
    def _mark_user_online_fallback(user_id: int) -> bool:
        state = OnlineUserService._get_fallback_state()
        key = str(user_id)
        entry = state.get(key, {"count": 0, "expires_at": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["expires_at"] = OnlineUserService._now_ts() + OnlineUserService.ONLINE_TTL_SECONDS
        state[key] = entry
        OnlineUserService._set_fallback_state(state)
        return entry["count"] == 1

    @staticmethod
    def _touch_user_online_fallback(user_id: int) -> bool:
        state = OnlineUserService._get_fallback_state()
        key = str(user_id)
        entry = state.get(key)
        if not entry:
            return False

        entry["expires_at"] = OnlineUserService._now_ts() + OnlineUserService.ONLINE_TTL_SECONDS
        state[key] = entry
        OnlineUserService._set_fallback_state(state)
        return True

    @staticmethod
    def _mark_user_offline_fallback(user_id: int) -> bool:
        state = OnlineUserService._get_fallback_state()
        key = str(user_id)
        entry = state.get(key)
        if not entry:
            return False

        count = int(entry.get("count", 0))
        if count <= 1:
            state.pop(key, None)
            OnlineUserService._set_fallback_state(state)
            return True

        entry["count"] = count - 1
        entry["expires_at"] = OnlineUserService._now_ts() + OnlineUserService.ONLINE_TTL_SECONDS
        state[key] = entry
        OnlineUserService._set_fallback_state(state)
        return False

    @staticmethod
    def _get_online_user_ids_fallback(limit: int) -> List[int]:
        state = OnlineUserService._get_fallback_state()
        ordered_ids = sorted(
            state.keys(),
            key=lambda user_id: state[user_id]["expires_at"],
            reverse=True,
        )
        return [int(user_id) for user_id in ordered_ids[:limit]]

    @staticmethod
    def _get_fallback_state() -> Dict[str, dict]:
        state = cache.get(OnlineUserService.FALLBACK_CACHE_KEY, {}) or {}
        return OnlineUserService._prune_fallback_state(state)

    @staticmethod
    def _set_fallback_state(state: Dict[str, dict]) -> None:
        cache.set(
            OnlineUserService.FALLBACK_CACHE_KEY,
            state,
            OnlineUserService.ONLINE_TTL_SECONDS,
        )

    @staticmethod
    def _prune_fallback_state(state: Dict[str, dict]) -> Dict[str, dict]:
        now = OnlineUserService._now_ts()
        return {
            user_id: entry
            for user_id, entry in state.items()
            if int(entry.get("expires_at", 0)) > now and int(entry.get("count", 0)) > 0
        }

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

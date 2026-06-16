from __future__ import annotations

from typing import Any


MIN_HS256_KEY_LENGTH = 32
KNOWN_PLACEHOLDER_SECRETS = {
    "django-insecure-change-this-in-production",
    "jwt-secret-key-change-this",
}


def normalize_secret_value(value: Any) -> str:
    return str(value or "").strip()


def looks_like_placeholder_secret(value: Any) -> bool:
    normalized = normalize_secret_value(value).lower()
    return (
        not normalized
        or normalized in KNOWN_PLACEHOLDER_SECRETS
        or "change-this" in normalized
        or normalized.startswith("replace-with")
    )


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
    normalized_secret_key = normalize_secret_value(secret_key)
    normalized_jwt_signing_key = normalize_secret_value(jwt_signing_key)
    jwt_required_length = jwt_key_length_requirement(jwt_algorithm)

    if looks_like_placeholder_secret(normalized_secret_key):
        risks.append(
            {
                "code": "django-secret-placeholder",
                "level": "danger",
                "title": "Django SECRET_KEY 仍为默认占位值",
                "message": "当前 SECRET_KEY 仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if looks_like_placeholder_secret(normalized_jwt_signing_key):
        risks.append(
            {
                "code": "jwt-secret-placeholder",
                "level": "danger",
                "title": "JWT 签名密钥仍为默认占位值",
                "message": "当前 JWT 签名密钥仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if jwt_required_length and len(normalized_jwt_signing_key) < jwt_required_length:
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

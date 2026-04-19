from __future__ import annotations

import httpx

from apps.core.settings_service import get_advanced_settings


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class HumanVerificationError(ValueError):
    status_code = 400


class HumanVerificationUnavailableError(HumanVerificationError):
    status_code = 503


def get_human_verification_settings() -> dict:
    advanced_settings = get_advanced_settings()
    return {
        "provider": str(advanced_settings.get("auth_human_verification_provider") or "off").strip().lower(),
        "turnstile_site_key": str(advanced_settings.get("auth_turnstile_site_key") or "").strip(),
        "turnstile_secret_key": str(advanced_settings.get("auth_turnstile_secret_key") or "").strip(),
        "login_enabled": bool(advanced_settings.get("auth_human_verification_login_enabled", True)),
        "register_enabled": bool(advanced_settings.get("auth_human_verification_register_enabled", True)),
    }


def should_enforce_human_verification(action: str) -> bool:
    config = get_human_verification_settings()
    if config["provider"] != "turnstile":
        return False
    if not config["turnstile_site_key"] or not config["turnstile_secret_key"]:
        return False
    if action == "login":
        return config["login_enabled"]
    if action == "register":
        return config["register_enabled"]
    return False


def get_request_ip(request) -> str:
    forwarded_for = str(request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return str(
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR")
        or ""
    ).strip()


def verify_human_verification(request, action: str, token: str | None) -> None:
    if not should_enforce_human_verification(action):
        return

    verification_token = str(token or "").strip()
    if not verification_token:
        raise HumanVerificationError("请先完成真人验证")

    config = get_human_verification_settings()
    _verify_turnstile_token(
        secret_key=config["turnstile_secret_key"],
        token=verification_token,
        remote_ip=get_request_ip(request),
    )


def _verify_turnstile_token(secret_key: str, token: str, remote_ip: str = "") -> None:
    payload = {
        "secret": secret_key,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = httpx.post(
            TURNSTILE_VERIFY_URL,
            data=payload,
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HumanVerificationUnavailableError("真人验证服务暂时不可用，请稍后再试") from exc

    if result.get("success"):
        return

    error_codes = result.get("error-codes") or []
    if "timeout-or-duplicate" in error_codes:
        raise HumanVerificationError("真人验证已过期，请重新完成验证")

    raise HumanVerificationError("真人验证失败，请重试")

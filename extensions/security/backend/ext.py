from apps.core.extensions import AuthExtender, FrontendExtender, LifecycleExtender, SettingsExtender
from extensions.security.backend.human_verification import (
    serialize_public_human_verification_setting,
    verify_human_verification,
)


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/security/frontend/admin/index.js",
            forum_entry="extensions/security/frontend/forum/index.js",
        ),
        build_human_verification_settings_extender(),
        AuthExtender().human_verification(
            "turnstile",
            verify_human_verification,
            description="在登录和注册流程中校验 Cloudflare Turnstile token。",
        ),
        LifecycleExtender(),
    ]


def build_human_verification_settings_extender():
    return (
        SettingsExtender(generated_page=False)
        .default("advanced.auth_human_verification_provider", "off")
        .default("advanced.auth_turnstile_site_key", "")
        .default("advanced.auth_turnstile_secret_key", "")
        .default("advanced.auth_human_verification_login_enabled", True)
        .default("advanced.auth_human_verification_register_enabled", True)
        .serialize_to_forum(
            "auth_human_verification_provider",
            "advanced.auth_human_verification_provider",
            serialize_public_human_verification_setting("auth_human_verification_provider"),
        )
        .serialize_to_forum(
            "auth_turnstile_site_key",
            "advanced.auth_turnstile_site_key",
            serialize_public_human_verification_setting("auth_turnstile_site_key"),
        )
        .serialize_to_forum(
            "auth_human_verification_login_enabled",
            "advanced.auth_human_verification_login_enabled",
            serialize_public_human_verification_setting("auth_human_verification_login_enabled"),
        )
        .serialize_to_forum(
            "auth_human_verification_register_enabled",
            "advanced.auth_human_verification_register_enabled",
            serialize_public_human_verification_setting("auth_human_verification_register_enabled"),
        )
    )

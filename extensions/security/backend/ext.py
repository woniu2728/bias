from apps.core.extensions import AuthExtender, FrontendExtender, LifecycleExtender, SettingsExtender, setting_field
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
        SettingsExtender(fields=human_verification_setting_definitions())
        .serialize_to_forum(
            "auth_human_verification_provider",
            "auth_human_verification_provider",
            serialize_public_human_verification_setting("auth_human_verification_provider"),
        )
        .serialize_to_forum(
            "auth_turnstile_site_key",
            "auth_turnstile_site_key",
            serialize_public_human_verification_setting("auth_turnstile_site_key"),
        )
        .serialize_to_forum(
            "auth_human_verification_login_enabled",
            "auth_human_verification_login_enabled",
            serialize_public_human_verification_setting("auth_human_verification_login_enabled"),
        )
        .serialize_to_forum(
            "auth_human_verification_register_enabled",
            "auth_human_verification_register_enabled",
            serialize_public_human_verification_setting("auth_human_verification_register_enabled"),
        )
    )


def human_verification_setting_definitions():
    return (
        setting_field({
            "key": "auth_human_verification_provider",
            "label": "真人验证提供方",
            "type": "select",
            "default": "off",
            "help_text": "选择登录和注册流程使用的真人验证服务。关闭时不会校验验证 token。",
            "options": [
                {"value": "off", "label": "关闭"},
                {"value": "turnstile", "label": "Cloudflare Turnstile"},
            ],
            "order": 10,
        }),
        setting_field({
            "key": "auth_turnstile_site_key",
            "label": "Turnstile Site Key",
            "type": "text",
            "default": "",
            "placeholder": "0x4AAAA...",
            "help_text": "前台渲染 Turnstile 挑战使用的公开站点密钥。",
            "order": 20,
        }),
        setting_field({
            "key": "auth_turnstile_secret_key",
            "label": "Turnstile Secret Key",
            "type": "text",
            "default": "",
            "placeholder": "0x4AAAA...",
            "help_text": "服务端向 Cloudflare 校验 token 使用的私密密钥。",
            "order": 30,
        }),
        setting_field({
            "key": "auth_human_verification_login_enabled",
            "label": "登录时启用真人验证",
            "type": "boolean",
            "default": True,
            "help_text": "开启后，登录请求需要携带有效真人验证 token。",
            "order": 40,
        }),
        setting_field({
            "key": "auth_human_verification_register_enabled",
            "label": "注册时启用真人验证",
            "type": "boolean",
            "default": True,
            "help_text": "开启后，注册请求需要携带有效真人验证 token。",
            "order": 50,
        }),
    )

from apps.core.extensions import ApiRoutesExtender, FrontendExtender, LifecycleExtender, ServiceProviderExtender, SettingsExtender, setting_field
from extensions.ai.backend.api import router as ai_router
from extensions.ai.backend.runtime import ai_service_provider


EXTENSION_ID = "ai"


def extend():
    return [
        FrontendExtender(
            forum_entry="extensions/ai/frontend/forum/index.js",
        ),
        ApiRoutesExtender(
            mounts=(("", ai_router),),
            tags=("AI",),
        ),
        ServiceProviderExtender(
            key="ai.service",
            provider=ai_service_provider,
        ),
        SettingsExtender(fields=setting_definitions(), expose_to_forum=(
            "enabled",
            "fallback_enabled",
            "model",
        ))
        .default("enabled", True)
        .default("base_url", "")
        .default("api_key", "")
        .default("model", "gpt-4.1-mini")
        .default("timeout_seconds", 30)
        .default("temperature_tenths", 4)
        .default("fallback_enabled", True),
        LifecycleExtender(),
    ]


def setting_definitions():
    return (
        setting_field({
            "key": "enabled",
            "label": "启用 AI 功能",
            "type": "boolean",
            "default": True,
            "help_text": "关闭后前台 AI 入口仍可显示占位反馈，但不会调用远程模型。",
            "order": 5,
        }),
        setting_field({
            "key": "base_url",
            "label": "AI Base URL",
            "type": "text",
            "default": "",
            "placeholder": "https://api.openai.com/v1",
            "help_text": "兼容 OpenAI Chat Completions 协议的服务地址，不包含 /chat/completions。",
            "order": 10,
        }),
        setting_field({
            "key": "api_key",
            "label": "AI API Key",
            "type": "text",
            "default": "",
            "placeholder": "sk-...",
            "help_text": "用于调用 AI 服务的密钥。当前由站点管理员保存，请注意部署环境访问控制。",
            "order": 20,
        }),
        setting_field({
            "key": "model",
            "label": "模型名称",
            "type": "text",
            "default": "gpt-4.1-mini",
            "help_text": "传给 Chat Completions API 的 model 字段。",
            "order": 30,
        }),
        setting_field({
            "key": "timeout_seconds",
            "label": "请求超时（秒）",
            "type": "number",
            "default": 30,
            "help_text": "AI 接口请求超时时间，建议 10-60 秒。",
            "order": 40,
        }),
        setting_field({
            "key": "temperature_tenths",
            "label": "创造性（0-15）",
            "type": "number",
            "default": 4,
            "help_text": "按十分位配置 temperature，例如 4 表示 0.4。",
            "order": 50,
        }),
        setting_field({
            "key": "fallback_enabled",
            "label": "未配置时启用本地占位反馈",
            "type": "boolean",
            "default": True,
            "help_text": "未设置 Base URL 或 API Key 时返回本地结构化建议，便于先体验流程。",
            "order": 60,
        }),
    )

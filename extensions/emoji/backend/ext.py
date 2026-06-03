import re

from apps.core.extensions import FormatterExtender, FrontendExtender, LifecycleExtender, LocalesExtender, SettingsExtender
from apps.core.extensions.backend import _build_setting_field_definition


EXTENSION_ID = "emoji"


def extend():
    return [
        FrontendExtender(
            forum_entry="extensions/emoji/frontend/forum/index.js",
        ),
        LocalesExtender(paths=(
            "extensions/emoji/locale",
        )),
        SettingsExtender(fields=(
            _build_setting_field_definition({
                "key": "cdn_url",
                "label": "Twemoji CDN",
                "type": "text",
                "default": "",
                "placeholder": "留空时使用默认 Twemoji CDN",
                "help_text": "用于覆盖表情图片资源地址。",
                "order": 10,
            }),
        ), expose_to_forum=("cdn_url",)),
        FormatterExtender(transforms=(
            render_emoji_html,
        )),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


EMOJI_PATTERN = re.compile(r"(?<![\w/])(:\)|:D|:P|:\(|:\||;\)|:'\(|:O|>:\()")
EMOJI_MAP = {
    ":)": "\U0001f642",
    ":D": "\U0001f603",
    ":P": "\U0001f61b",
    ":(": "\U0001f641",
    ":|": "\U0001f610",
    ";)": "\U0001f609",
    ":'(": "\U0001f622",
    ":O": "\U0001f62e",
    ">:(": "\U0001f621",
}


def render_emoji_html(html: str) -> str:
    return EMOJI_PATTERN.sub(lambda match: EMOJI_MAP.get(match.group(1), match.group(1)), html or "")


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Emoji 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Emoji 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Emoji 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Emoji 扩展已卸载。",
    }

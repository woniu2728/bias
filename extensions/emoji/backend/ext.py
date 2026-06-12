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
        ), expose_to_forum=("cdn_url",))
        .default("cdn_url", "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/")
        .reset_when("cdn_url", lambda value: not str(value or "").strip())
        .reset_frontend_cache_for("cdn_url")
        .theme_variable("bias-emoji-cdn", "cdn_url"),
        FormatterExtender().parse(parse_emoticons),
        LifecycleExtender(),
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


def parse_emoticons(text: str) -> str:
    return EMOJI_PATTERN.sub(lambda match: EMOJI_MAP.get(match.group(1), match.group(1)), text or "")

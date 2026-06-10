import json
from unittest.mock import patch

from django.test import TestCase

from apps.core.extension_settings_service import get_extension_settings, save_extension_settings
from apps.core.extensions.settings_runtime_service import (
    get_enabled_extension_settings_definitions,
    get_extension_settings_definition,
)
from apps.core.models import Setting
from apps.core.settings_service import clear_runtime_setting_caches


class EmojiExtensionTests(TestCase):
    def setUp(self):
        clear_runtime_setting_caches()

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_public_forum_settings_expose_emoji_frontend_and_forum_settings(self):
        Setting.objects.update_or_create(
            key="extensions.emoji.cdn_url",
            defaults={"value": json.dumps("https://cdn.example.com/twemoji/")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        emoji_extension = next(item for item in payload["enabled_extensions"] if item["id"] == "emoji")
        self.assertEqual(emoji_extension["frontend_forum_entry"], "extensions/emoji/frontend/forum/index.js")
        self.assertEqual(emoji_extension["settings_values"]["cdn_url"], "https://cdn.example.com/twemoji/")
        self.assertEqual(emoji_extension["forum_settings"], {"cdn_url": "https://cdn.example.com/twemoji/"})
        self.assertTrue(any(
            item["extension_id"] == "emoji"
            and item["locale"] == "zh-CN"
            and item["messages"].get("emoji.toolbar.title") == "表情"
            for item in payload["extension_locales"]
        ))

    def test_settings_runtime_service_exposes_emoji_settings_definition(self):
        definitions = get_enabled_extension_settings_definitions()
        emoji = get_extension_settings_definition("emoji")

        self.assertIn("emoji", definitions)
        self.assertEqual(emoji["defaults"]["cdn_url"], "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/")
        self.assertEqual(emoji["forum_settings_keys"], ("cdn_url",))
        self.assertEqual(emoji["fields"][0].key, "cdn_url")

    def test_markdown_preview_applies_emoji_formatter_pipeline(self):
        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "今天真开心 :)"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("🙂", response.json()["html"])

    @patch("apps.core.extensions.lifecycle.invalidate_extension_frontend_assets")
    @patch("apps.core.extensions.frontend_runtime_service.clear_extension_frontend_runtime_cache")
    def test_extension_settings_default_reset_and_frontend_cache_invalidation(
        self,
        clear_frontend_runtime_cache,
        invalidate_frontend_assets,
    ):
        default_cdn = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"

        self.assertEqual(get_extension_settings("emoji")["cdn_url"], default_cdn)

        saved = save_extension_settings("emoji", {"cdn_url": "https://cdn.example.com/twemoji/"})

        self.assertEqual(saved["cdn_url"], "https://cdn.example.com/twemoji/")
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.emoji.cdn_url").value),
            "https://cdn.example.com/twemoji/",
        )
        clear_frontend_runtime_cache.assert_called()
        invalidate_frontend_assets.assert_called_with(
            "extension_settings_changed",
            extension_id="emoji",
        )

        clear_frontend_runtime_cache.reset_mock()
        invalidate_frontend_assets.reset_mock()

        reset = save_extension_settings("emoji", {"cdn_url": ""})

        self.assertEqual(reset["cdn_url"], default_cdn)
        self.assertFalse(Setting.objects.filter(key="extensions.emoji.cdn_url").exists())
        clear_frontend_runtime_cache.assert_called()
        invalidate_frontend_assets.assert_called_with(
            "extension_settings_changed",
            extension_id="emoji",
        )

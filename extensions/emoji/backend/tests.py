import json

from django.test import TestCase

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

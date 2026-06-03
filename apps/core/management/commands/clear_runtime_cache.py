from __future__ import annotations

from django.core.cache import cache
from django.core.management import BaseCommand

from apps.core.extensions.event_bus import get_extension_event_bus
from apps.core.extensions.events import RuntimeCacheClearedEvent
from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners
from apps.core.settings_service import clear_runtime_setting_caches


class Command(BaseCommand):
    help = "清理论坛运行时缓存与设置缓存。"

    def handle(self, *args, **options):
        try:
            cache.clear()
        except Exception:
            self.stdout.write("[WARN] Django cache.clear() 执行失败，继续清理设置缓存")

        clear_runtime_setting_caches()
        bootstrap_extension_runtime_event_listeners()
        get_extension_event_bus().dispatch(RuntimeCacheClearedEvent())
        self.stdout.write(self.style.SUCCESS("[OK] 已清理运行时缓存"))

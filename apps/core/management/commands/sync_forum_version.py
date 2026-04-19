from django.core.management import BaseCommand

from apps.core.runtime_state import sync_installed_version


class Command(BaseCommand):
    help = "同步当前代码版本到系统设置。"

    def handle(self, *args, **options):
        version = sync_installed_version()
        self.stdout.write(self.style.SUCCESS(f"[OK] 已同步系统版本: {version}"))


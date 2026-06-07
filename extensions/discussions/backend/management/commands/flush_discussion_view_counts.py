from django.core.management.base import BaseCommand

from apps.discussions.services import DiscussionService


class Command(BaseCommand):
    help = "将缓存中累积的讨论浏览量写回数据库"

    def handle(self, *args, **options):
        flushed_count = DiscussionService.flush_all_pending_view_counts()
        self.stdout.write(self.style.SUCCESS(f"已写回 {flushed_count} 次讨论浏览量"))

from django.core.management.base import BaseCommand

from extensions.tags.backend.services import TagService


class Command(BaseCommand):
    help = "重新计算标签讨论数和最后发帖讨论"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag-id",
            action="append",
            type=int,
            dest="tag_ids",
            help="只刷新指定标签，可重复传入。不传则刷新全部标签。",
        )

    def handle(self, *args, **options):
        tag_ids = options.get("tag_ids")
        TagService.refresh_tag_stats(tag_ids)
        if tag_ids:
            self.stdout.write(self.style.SUCCESS(f"已刷新 {len(set(tag_ids))} 个标签统计"))
        else:
            self.stdout.write(self.style.SUCCESS("已刷新全部标签统计"))

from celery import shared_task

from extensions.discussions.backend.services import DiscussionService


@shared_task(ignore_result=True)
def flush_discussion_view_count_task(discussion_id: int):
    DiscussionService.flush_pending_view_count(discussion_id)

from celery import shared_task

from extensions.notifications.backend.services import NotificationService


@shared_task(ignore_result=True)
def dispatch_notification_batch(notification_ids):
    NotificationService.load_notifications_for_realtime(notification_ids or [])

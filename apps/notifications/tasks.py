from celery import shared_task

from extensions.notifications.backend.services import NotificationService


@shared_task(ignore_result=True)
def dispatch_notification_batch(notification_ids):
    NotificationService._send_notifications_batch(notification_ids or [])

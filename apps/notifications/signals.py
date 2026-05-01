from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService


@receiver(post_save, sender=Notification)
def invalidate_unread_count_on_save(sender, instance, **kwargs):
    NotificationService.invalidate_unread_count(instance.user_id)


@receiver(post_delete, sender=Notification)
def invalidate_unread_count_on_delete(sender, instance, **kwargs):
    NotificationService.invalidate_unread_count(instance.user_id)

from extensions.notifications.backend.services import NotificationService


def invalidate_unread_count_on_save(sender, instance, **kwargs):
    NotificationService.invalidate_unread_count(instance.user_id)


def invalidate_unread_count_on_delete(sender, instance, **kwargs):
    NotificationService.invalidate_unread_count(instance.user_id)

from django.apps import AppConfig


class TagsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "tags"
    name = "extensions.tags.backend"
    verbose_name = "Bias Tags Extension"

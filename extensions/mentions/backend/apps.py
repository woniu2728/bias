from django.apps import AppConfig


class MentionsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "mentions"
    name = "extensions.mentions.backend"
    verbose_name = "Bias Mentions Extension"

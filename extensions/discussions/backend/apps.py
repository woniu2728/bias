from django.apps import AppConfig


class DiscussionsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "extensions.discussions.backend"
    label = "discussions"
    verbose_name = "Bias Discussions"

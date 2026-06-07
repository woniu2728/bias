from django.apps import AppConfig


class PostsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts"
    label = "posts"
    verbose_name = "Bias Posts"

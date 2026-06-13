from django.apps import AppConfig


class PointsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "points"
    name = "extensions.points.backend"
    verbose_name = "Bias Points Extension"


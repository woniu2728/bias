from django.apps import AppConfig


class FlagsExtensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "flags"
    name = "extensions.flags.backend"
    verbose_name = "Bias Flags Extension"

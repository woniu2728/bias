from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from django.db.backends.signals import connection_created
        from apps.core.forum_event_listeners import bootstrap_forum_event_listeners
        from apps.core.forum_registry import get_forum_registry
        from apps.core.forum_resources import bootstrap_forum_resource_fields

        # Ensure builtin modules are registered during app startup.
        get_forum_registry()
        bootstrap_forum_event_listeners()
        bootstrap_forum_resource_fields()

        connection_created.connect(
            configure_sqlite_pragmas,
            dispatch_uid="bias.configure_sqlite_pragmas",
        )


def configure_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return

    if getattr(connection, "_bias_sqlite_configured", False):
        return

    try:
        with connection.cursor() as cursor:
            # WAL lets reads and writes overlap better in the local SQLite dev setup.
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=10000;")
    except Exception:
        return

    connection._bias_sqlite_configured = True

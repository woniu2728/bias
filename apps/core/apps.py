from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from django.db.backends.signals import connection_created

        connection_created.connect(
            configure_sqlite_pragmas,
            dispatch_uid="pyflarum.configure_sqlite_pragmas",
        )


def configure_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return

    if getattr(connection, "_pyflarum_sqlite_configured", False):
        return

    try:
        with connection.cursor() as cursor:
            # WAL lets reads and writes overlap better in the local SQLite dev setup.
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        return

    connection._pyflarum_sqlite_configured = True

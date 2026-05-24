from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_postgres_search_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExtensionInstallation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("extension_id", models.CharField(db_index=True, max_length=120, unique=True)),
                ("version", models.CharField(blank=True, max_length=32)),
                ("source", models.CharField(default="filesystem", max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("installed", models.BooleanField(default=True)),
                ("booted", models.BooleanField(default=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "extension_installations",
                "ordering": ["extension_id"],
            },
        ),
        migrations.AddIndex(
            model_name="extensioninstallation",
            index=models.Index(fields=["extension_id"], name="extension_in_extensi_170d92_idx"),
        ),
        migrations.AddIndex(
            model_name="extensioninstallation",
            index=models.Index(fields=["enabled"], name="extension_in_enabled_4a7295_idx"),
        ),
        migrations.AddIndex(
            model_name="extensioninstallation",
            index=models.Index(fields=["installed"], name="extension_in_installe_2c2d6e_idx"),
        ),
    ]

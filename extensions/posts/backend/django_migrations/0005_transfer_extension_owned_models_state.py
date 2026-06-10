from django.db import migrations


MODEL_APP_LABEL_TRANSFERS = (
    ("posts", "postflag", "flags"),
    ("posts", "postlike", "likes"),
    ("posts", "postmentionsuser", "mentions"),
)


def transfer_content_types(apps, schema_editor):
    _transfer_content_type_labels(apps, MODEL_APP_LABEL_TRANSFERS)


def restore_content_types(apps, schema_editor):
    _transfer_content_type_labels(
        apps,
        tuple((new_app_label, model, old_app_label) for old_app_label, model, new_app_label in MODEL_APP_LABEL_TRANSFERS),
    )


def _transfer_content_type_labels(apps, transfers):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    for old_app_label, model, new_app_label in transfers:
        old_content_type = ContentType.objects.filter(app_label=old_app_label, model=model).first()
        if old_content_type is None:
            continue

        target_content_type = ContentType.objects.filter(app_label=new_app_label, model=model).first()
        if target_content_type is not None and target_content_type.pk != old_content_type.pk:
            Permission.objects.filter(content_type=old_content_type).update(content_type=target_content_type)
            old_content_type.delete()
            continue

        old_content_type.app_label = new_app_label
        old_content_type.save(update_fields=["app_label"])


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("posts", "0004_post_approval_status"),
        ("flags", "0001_state_post_flag"),
        ("likes", "0001_state_post_like"),
        ("mentions", "0001_state_post_mentions_user"),
    ]

    operations = [
        migrations.RunPython(transfer_content_types, restore_content_types),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="PostFlag"),
                migrations.DeleteModel(name="PostLike"),
                migrations.DeleteModel(name="PostMentionsUser"),
            ],
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tags", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="reply_scope",
            field=models.CharField(
                choices=[("public", "所有人"), ("members", "已登录用户"), ("staff", "仅管理员")],
                default="members",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="tag",
            name="start_discussion_scope",
            field=models.CharField(
                choices=[("public", "所有人"), ("members", "已登录用户"), ("staff", "仅管理员")],
                default="members",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="tag",
            name="view_scope",
            field=models.CharField(
                choices=[("public", "所有人"), ("members", "已登录用户"), ("staff", "仅管理员")],
                default="public",
                max_length=20,
            ),
        ),
    ]

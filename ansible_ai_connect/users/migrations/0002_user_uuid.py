# Generated by Django 4.1.3 on 2023-03-09 18:48

import uuid

from django.db import migrations, models


def gen_uuid(apps, schema_editor):
    User = apps.get_model("users", "User")
    for row in User.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, null=True, editable=False),
        ),
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(unique=True, default=uuid.uuid4, editable=False),
        ),
    ]

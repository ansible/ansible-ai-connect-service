# Generated manually to create new Organization model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_organization_enable_anonymization"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(help_text="The name of this organization.", max_length=512)),
                (
                    "description",
                    models.TextField(blank=True, default="", help_text="The organization description."),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
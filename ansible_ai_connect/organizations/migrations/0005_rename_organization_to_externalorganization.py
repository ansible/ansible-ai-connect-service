# Generated migration to rename Organization model to ExternalOrganization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_organization_enable_anonymization"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Organization",
            new_name="ExternalOrganization",
        ),
    ]

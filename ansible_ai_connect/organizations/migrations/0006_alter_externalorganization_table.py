# Generated manually to rename ExternalOrganization table to organizations_organization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0005_organization"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="externalorganization",
            table="organizations_organization",
        ),
    ]
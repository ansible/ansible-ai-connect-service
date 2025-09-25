# Generated manually to create new Organization model and clear dab_rbac data

import logging
from django.db import migrations

logger = logging.getLogger(__name__)


def clear_dab_rbac_data(apps, schema_editor):
    """Delete all entries from dab_rbac models"""
    db_alias = schema_editor.connection.alias

    # Get all dab_rbac models
    from django.apps import apps as django_apps

    dab_rbac_config = django_apps.get_app_config("dab_rbac")

    # Delete all data from dab_rbac models in reverse dependency order
    for model in reversed(dab_rbac_config.get_models()):
        count = model.objects.using(db_alias).count()
        if count > 0:
            logger.warning(
                "Migration 0005_migration_data_fix: Deleting %d entries from model %s",
                count,
                model.__name__
            )
        model.objects.using(db_alias).all().delete()


def reverse_clear_dab_rbac_data(apps, schema_editor):
    """Reverse operation - no-op since we can't restore deleted data"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_organization_enable_anonymization"),
        ("dab_rbac", "0004_remote_permissions_additions"),
    ]

    run_before = [
        ("dab_rbac", "0005_remote_permissions_data"),
    ]

    operations = [
        migrations.RunPython(
            clear_dab_rbac_data,
            reverse_clear_dab_rbac_data,
        ),
    ]

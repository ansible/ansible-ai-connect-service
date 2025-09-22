from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial"), ("users", "0009_user_organization")]

    operations = [
        migrations.RunSQL(
            """
            insert into
            organizations_externalorganization
            select
            organization_id, false
            from
            users_user
            where
            organization_id is not null
            on conflict (id) do nothing;
            update
            users_user
            set
            fk_organization_id = organization_id
            where
            organization_id is not null;
            """
        )
    ]

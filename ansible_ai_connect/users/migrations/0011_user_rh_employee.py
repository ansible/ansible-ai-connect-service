# Generated by Django 4.2.11 on 2024-07-19 17:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_plan_userplan_user_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="rh_employee",
            field=models.BooleanField(default=False),
        ),
    ]
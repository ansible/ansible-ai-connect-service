from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ansible_wisdom.users'

    def ready(self) -> None:
        import ansible_wisdom.users.signals  # noqa: F401

from ai.api.ansible.model import AnsibleModel
from django.apps import AppConfig
from django.conf import settings


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model = AnsibleModel()

    def ready(self) -> None:
        checkpoint_location = settings.ANSIBLE_WISDOM_AI_CHECKPOINT_PATH
        if not checkpoint_location:
            raise ValueError("ANSIBLE_WISDOM_AI_CHECKPOINT_PATH is not set")
        self.model.load_model(checkpoint_location)
        return super().ready()

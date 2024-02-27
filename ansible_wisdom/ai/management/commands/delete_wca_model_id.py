from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes
from ansible_wisdom.ai.management.commands._base_wca_delete_command import (
    BaseWCADeleteCommand,
)


class Command(BaseWCADeleteCommand):
    help = "Delete WCA Model Id for OrgId"

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.MODEL_ID

    def get_success_message(self, org_id) -> str:
        return f"Model Id for orgId '{org_id}' deleted."

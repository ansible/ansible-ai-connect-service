from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes
from ansible_wisdom.ai.management.commands._base_wca_post_command import (
    BaseWCAPostCommand,
)


class Command(BaseWCAPostCommand):
    help = "Create WCA Model Id for OrgId"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('secret', type=str, help="IBM WCA Model Id")

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.MODEL_ID

    def get_success_message(self, org_id, key_name) -> str:
        return f"Model Id for orgId '{org_id}' stored as: {key_name}"

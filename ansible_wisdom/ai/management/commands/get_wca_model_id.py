from ai.api.aws.wca_secret_manager import Suffixes
from ai.management.commands._base_wca_get_command import BaseWCAGetCommand


class Command(BaseWCAGetCommand):
    help = "Get WCA Model Id for OrgId"

    def add_arguments(self, parser):
        parser.add_argument(
            "org_id", type=str, help="The Red Hat OrgId that the ModelId belongs to"
        )

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.MODEL_ID

    def get_message_found(self, org_id, response) -> str:
        message = f"Model id for orgId '{org_id}' found. "
        f"Id: {response['model_id']}, Last updated: {response['CreatedDate']}"
        return message

    def get_message_not_found(self, org_id) -> str:
        return f"No Model Id for orgId '{org_id}' found."

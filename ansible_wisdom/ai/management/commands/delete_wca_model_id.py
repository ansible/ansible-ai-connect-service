from ai.api.aws.wca_secret_manager import Suffixes
from ai.management.commands._base_wca_delete_command import BaseWCADeleteCommand


class Command(BaseWCADeleteCommand):
    help = "Delete WCA Model Id for OrgId"

    def add_arguments(self, parser):
        parser.add_argument(
            "org_id", type=str, help="The Red Hat OrgId that the Model Id belongs to"
        )

    def __get_secret_suffix(self) -> Suffixes:
        return Suffixes.MODEL_ID

    def __get_success_message(self, org_id) -> str:
        return f"Model Id for orgId '{org_id}' deleted."

from ai.api.aws.wca_secret_manager import Suffixes
from ai.management.commands._base_wca_delete_command import BaseWCADeleteCommand


class Command(BaseWCADeleteCommand):
    help = "Delete WCA API Key for OrgId"

    def add_arguments(self, parser):
        parser.add_argument(
            "org_id", type=str, help="The Red Hat OrgId that the API Key belongs to"
        )

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.API_KEY

    def get_success_message(self, org_id) -> str:
        return f"API Key for orgId '{org_id}' deleted."

from ai.api.aws.wca_secret_manager import Suffixes
from ai.management.commands._base_wca_post_command import BaseWCAPostCommand


class Command(BaseWCAPostCommand):
    help = "Create WCA API Key for OrgId"

    def add_arguments(self, parser):
        parser.add_argument(
            "org_id", type=str, help="The Red Hat OrgId that the API Key belongs to"
        )
        parser.add_argument('secret', type=str, help="IBM WCA API Key")

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.API_KEY

    def get_success_message(self, org_id, key_name) -> str:
        return f"API Key for orgId '{org_id}' stored as: {key_name}"

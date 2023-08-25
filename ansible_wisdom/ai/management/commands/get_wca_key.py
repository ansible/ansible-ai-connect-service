from ai.api.aws.wca_secret_manager import Suffixes
from ai.management.commands._base_wca_get_command import BaseWCAGetCommand


class Command(BaseWCAGetCommand):
    help = "Get WCA API Key for OrgId"

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.API_KEY

    def get_message_found(self, org_id, response) -> str:
        return f"API Key for orgId '{org_id}' found. Last updated: {response['CreatedDate']}"

    def get_message_not_found(self, org_id) -> str:
        return f"No API Key for orgId '{org_id}' found."

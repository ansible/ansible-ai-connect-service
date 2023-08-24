from ai.api.aws.wca_secret_manager import (
    Suffixes,
    WcaSecretManager,
    WcaSecretManagerError,
)
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create WCA API Key for OrgId"

    def add_arguments(self, parser):
        parser.add_argument(
            "org_id", type=str, help="The Red Hat OrgId that the API Key belongs to"
        )
        parser.add_argument('key', type=str, help="IBM WCA API Key")

    def handle(self, *args, **options):
        org_id = options["org_id"]
        key = options["key"]

        client = WcaSecretManager(
            settings.WCA_SECRET_MANAGER_ACCESS_KEY,
            settings.WCA_SECRET_MANAGER_SECRET_ACCESS_KEY,
            settings.WCA_SECRET_MANAGER_KMS_KEY_ID,
            settings.WCA_SECRET_MANAGER_PRIMARY_REGION,
            settings.WCA_SECRET_MANAGER_REPLICA_REGIONS,
        )

        self.stdout.write(f"Using AWS Primary Region: {settings.WCA_SECRET_MANAGER_PRIMARY_REGION}")
        self.stdout.write(
            f"Using AWS Replica Region(s): {settings.WCA_SECRET_MANAGER_REPLICA_REGIONS}"
        )

        try:
            key_name = client.save_secret(org_id, Suffixes.API_KEY, key)
            self.stdout.write(f"API Key for orgId '{org_id}' stored as: {key_name}")
        except WcaSecretManagerError as e:
            raise CommandError(e)

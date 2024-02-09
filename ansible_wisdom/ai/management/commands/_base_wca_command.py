from abc import abstractmethod

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ansible_wisdom.ai.api.aws.wca_secret_manager import (
    AWSSecretManager,
    Suffixes,
    WcaSecretManagerError,
)


class BaseWCACommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("org_id", type=str, help="The Red Hat OrgId.")

    def handle(self, *args, **options):
        client = AWSSecretManager(
            settings.WCA_SECRET_MANAGER_ACCESS_KEY,
            settings.WCA_SECRET_MANAGER_SECRET_ACCESS_KEY,
            settings.WCA_SECRET_MANAGER_KMS_KEY_ID,
            settings.WCA_SECRET_MANAGER_PRIMARY_REGION,
            settings.WCA_SECRET_MANAGER_REPLICA_REGIONS,
        )

        self.stdout.write(
            f"Using AWS Primary Region: {settings.WCA_SECRET_MANAGER_PRIMARY_REGION} and "
            f"AWS Replica Regions: {', '.join(settings.WCA_SECRET_MANAGER_REPLICA_REGIONS)}."
        )

        try:
            self.do_command(client, args, options)
        except WcaSecretManagerError as e:
            raise CommandError(e)

    @abstractmethod
    def do_command(self, client, args, options):
        pass

    @abstractmethod
    def get_secret_suffix(self) -> Suffixes:
        pass

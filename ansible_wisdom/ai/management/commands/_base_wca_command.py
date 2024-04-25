#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

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

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

from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes
from ansible_wisdom.ai.management.commands._base_wca_post_command import (
    BaseWCAPostCommand,
)


class Command(BaseWCAPostCommand):
    help = "Create WCA API Key for OrgId"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('secret', type=str, help="IBM WCA API Key")

    def get_secret_suffix(self) -> Suffixes:
        return Suffixes.API_KEY

    def get_success_message(self, org_id, key_name) -> str:
        return f"API Key for orgId '{org_id}' stored as: {key_name}"

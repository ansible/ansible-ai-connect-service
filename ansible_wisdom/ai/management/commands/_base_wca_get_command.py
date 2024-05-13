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

from ansible_ai_connect.ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCAGetCommand(BaseWCACommand):
    def do_command(self, client, args, options):
        org_id = options["org_id"]
        response = client.get_secret(org_id, self.get_secret_suffix())
        if response is None:
            self.stdout.write(self.get_message_not_found(org_id))
            return

        self.stdout.write(self.get_message_found(org_id, response))

    @abstractmethod
    def get_message_found(self, org_id, response) -> str:
        pass

    @abstractmethod
    def get_message_not_found(self, org_id) -> str:
        pass

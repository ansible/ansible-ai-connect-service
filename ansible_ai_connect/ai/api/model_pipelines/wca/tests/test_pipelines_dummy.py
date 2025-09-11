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

import json
from unittest.mock import Mock

from django.test import TestCase

from ansible_ai_connect.ai.api.model_pipelines.pipelines import RoleGenerationParameters
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
    WCADummyRoleGenerationPipeline,
)


class TestWCADummy(TestCase):
    def test_role_generation(self):
        self.maxDiff = None
        config = mock_pipeline_config("wca-dummy")
        model_client = WCADummyRoleGenerationPipeline(config)
        response = model_client.invoke(
            RoleGenerationParameters.init(request=Mock(), model_id=config.model_id)
        )
        expected = [
            {
                "path": "tasks/main.yml",
                "file_type": "task",
                "content": "- name: Install the Nginx packages\n"
                "  package:\n"
                '    name: "{{ install_nginx_packages }}"\n'
                "    state: present\n"
                "  become: true\n"
                "- name: Start the service\n"
                "  service:\n"
                "    name: nginx\n"
                "    enabled: true\n"
                "    state: started\n"
                "    become: true",
            },
            {
                "path": "defaults/main.yml",
                "file_type": "default",
                "content": "install_nginx_packages:\n  - nginx",
            },
        ]
        self.assertEqual(json.dumps(["install_nginx", expected, "", []]), json.dumps(response))

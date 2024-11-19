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
import logging
import secrets
import time

import requests

from ansible_ai_connect.ai.api.model_pipelines.dummy.configuration import (
    DummyConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

logger = logging.getLogger(__name__)

PLAYBOOK = """
```yaml
---
- hosts: rhel9
  become: yes
  tasks:
    - name: Install EPEL repository
      ansible.builtin.dnf:
        name: epel-release
        state: present

    - name: Update package list
      ansible.builtin.dnf:
        update_cache: yes

    - name: Install nginx
      ansible.builtin.dnf:
        name: nginx
        state: present

    - name: Start and enable nginx service
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: yes
```
"""

ROLES = "TMP_DUMP_ROLES"

ROLE_FILE = [
    {
        "path": "defaults/main.yml",
        "file_type": "default",
        "content": "install_nginx_packages:\n  - nginx",
    }
]

OUTLINE = """
1. First, ensure that your RHEL 9 system is up-to-date.
2. Next, you install the Nginx package using the package manager.
3. After installation, start the ginx service.
4. Ensure that Nginx starts automatically.
5. Check if Nginx is running successfully.
6. Visit your system's IP address followed by the default Nginx port number (80 or 443).
"""

EXPLANATION = """# Information
This playbook installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux (RHEL) 9.
"""


@Register(api_type="dummy")
class DummyMetaData(MetaData[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}


@Register(api_type="dummy")
class DummyCompletionsPipeline(DummyMetaData, ModelPipelineCompletions[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        logger.debug("!!!! settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == 'dummy' !!!!")
        logger.debug("!!!! Mocking Model response !!!!")
        if self.config.latency_use_jitter:
            jitter: float = secrets.randbelow(1000) * 0.001
        else:
            jitter: float = 0.001
        time.sleep(self.config.latency_max_msec * jitter)
        response_body = json.loads(self.config.body)
        response_body["model_id"] = "_"
        return response_body

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError

    def self_test(self):
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="dummy")
class DummyPlaybookGenerationPipeline(
    DummyMetaData, ModelPipelinePlaybookGeneration[DummyConfiguration]
):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        create_outline = params.create_outline
        if create_outline:
            return PLAYBOOK, OUTLINE, []
        return PLAYBOOK, "", []

    def self_test(self):
        raise NotImplementedError


@Register(api_type="dummy")
class DummyRoleGenerationPipeline(DummyMetaData, ModelPipelineRoleGeneration[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        create_outline = params.create_outline
        if create_outline:
            return ROLES, ROLE_FILE, OUTLINE
        return ROLES, ROLE_FILE, ""

    def self_test(self):
        raise NotImplementedError


@Register(api_type="dummy")
class DummyPlaybookExplanationPipeline(
    DummyMetaData, ModelPipelinePlaybookExplanation[DummyConfiguration]
):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        return EXPLANATION

    def self_test(self):
        raise NotImplementedError

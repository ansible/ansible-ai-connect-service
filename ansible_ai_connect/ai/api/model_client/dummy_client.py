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
from typing import Any, Dict

import requests
from django.conf import settings

from .base import ModelMeshClient

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


class DummyClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, request, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        logger.debug("!!!! settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == 'dummy' !!!!")
        logger.debug("!!!! Mocking Model response !!!!")
        if settings.DUMMY_MODEL_RESPONSE_LATENCY_USE_JITTER:
            jitter: float = secrets.randbelow(1000) * 0.001
        else:
            jitter: float = 0.001
        time.sleep(settings.DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC * jitter)
        response_body = json.loads(settings.DUMMY_MODEL_RESPONSE_BODY)
        response_body["model_id"] = "_"
        return response_body

    def generate_playbook(
        self,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
    ) -> tuple[str, str]:
        if create_outline:
            return PLAYBOOK, OUTLINE
        return PLAYBOOK, ""

    def explain_playbook(
        self, request, content: str, custom_prompt: str = "", explanation_id: str = ""
    ) -> str:
        return EXPLANATION

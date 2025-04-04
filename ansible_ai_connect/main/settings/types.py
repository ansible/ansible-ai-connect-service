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

from typing import Literal

# ==================================================================
# Types used by settings. Moved from base.py since various bits of
# code reference these types without needing the whole settings and
# lead to circular reference errors.
# ------------------------------------------------------------------
t_model_mesh_api_type = Literal[
    "http",
    "dummy",
    "wca",
    "wca-onprem",
    "wca-dummy",
    "ollama",
    "llamacpp",
    "nop",
    "llama-stack",
]

t_deployment_mode = Literal["saas", "upstream", "onprem"]

t_wca_secret_backend_type = Literal["dummy", "aws_sm"]

t_one_click_reports_postman_type = Literal[
    "none", "stdout", "slack-webhook", "slack-webapi", "google-drive"
]
# ==================================================================

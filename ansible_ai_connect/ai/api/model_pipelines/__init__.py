import ansible_ai_connect.ai.api.model_pipelines.dummy.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.http.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.http.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.llamacpp.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.nop.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.nop.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.ollama.configuration  # noqa
import ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.configuration_dummy  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.configuration_onprem  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.configuration_saas  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem  # noqa
import ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas  # noqa
from ansible_ai_connect.ai.api.model_pipelines.registry import set_defaults

set_defaults()

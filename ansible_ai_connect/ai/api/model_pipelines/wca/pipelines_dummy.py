import logging
from abc import ABCMeta
from typing import TYPE_CHECKING, Any, Dict, Optional

from ansible_ai_connect.ai.api.model_pipelines.exceptions import WcaTokenFailure
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipeline,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None

logger = logging.getLogger(__name__)


class WCADummyMetaData(MetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_model_id(
        self,
        user: User,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        return requested_model_id or ""

    def get_token(self, api_key) -> str:
        if api_key != "valid":
            raise WcaTokenFailure("I'm a fake WCA client and the only api_key I accept is 'valid'")
        return ""


class WCADummyPipeline(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


class WCADummyCompletionsPipeline(WCADummyPipeline, ModelPipelineCompletions):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def infer(self, request, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        return {
            "model_id": "mocked_wca_client",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }

    def infer_from_parameters(self, *args, **kwargs):
        return ""


class WCADummyContentMatchPipeline(WCADummyPipeline, ModelPipelineContentMatch):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def codematch(self, request, model_input, model_id):
        raise NotImplementedError


class WCADummyPlaybookGenerationPipeline(WCADummyPipeline, ModelPipelinePlaybookGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def generate_playbook(
        self,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ) -> tuple[str, str, list]:
        raise NotImplementedError


class WCADummyPlaybookExplanationPipeline(WCADummyPipeline, ModelPipelinePlaybookExplanation):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def explain_playbook(
        self,
        request,
        content: str,
        custom_prompt: str = "",
        explanation_id: str = "",
        model_id: str = "",
    ) -> str:
        raise NotImplementedError

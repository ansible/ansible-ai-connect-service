import logging
from django.apps import apps
from django.conf import settings


from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PipelineConfiguration,
)

logger = logging.getLogger(__name__)


import backoff

from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (

    ibm_cloud_identity_token_hist,
)


from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaKeyNotFound,
)

from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ContentMatchParameters,
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
    RoleExplanationParameters,
    RoleGenerationParameters,
    StreamingChatBotParameters,
)

def get_api_key(user, provider_name) -> str:
    organization_id = user.organization and user.organization.id


    if organization_id is None:
        logger.error(
            "User does not have an organization and WCASaaSConfiguration.api_key is not set"
        )
        raise WcaKeyNotFound


    from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY
    # if provider_name not in REGISTRY:
    #         logger.error(f"Provider '{provider_name}' is not available amoung: {sorted(REGISTRY.keys())}")
    #         raise WcaKeyNotFound

    config = apps.get_app_config("ai").get_model_pipeline(MetaData)
    print(config.config.inference_url)

    if (
        settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
        and any(up.is_active for up in user.userplan_set.all())
        and user.organization
        and not user.organization.has_api_key
    ):
        print("TRiaaaallalalalal")


    #return "TRIALLLAAAA"

    secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore

    try:
        api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
        if api_key is not None:
            return api_key["SecretString"]

    except (WcaSecretManagerError, KeyError):
        # if retrieving the API Key from AWS fails, we log an error
        logger.error(f"error retrieving WCA API Key for org_id '{organization_id}'")
        raise

    logger.error("Seated user's organization doesn't have default API Key set")
    raise WcaKeyNotFound
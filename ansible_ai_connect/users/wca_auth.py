import logging
from typing import Optional
from ansible_ai_connect.ai.api.views import WcaModelIdNotFound
from django.apps import apps
from django.conf import settings
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError


from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PipelineConfiguration,
)

logger = logging.getLogger(__name__)


from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (

    ibm_cloud_identity_token_hist,
)


from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaKeyNotFound,
)

from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (

    MetaData,
)

def get_api_key(user, provider_name) -> str:
    organization_id = user.organization and user.organization.id


    if organization_id is None:
        logger.error(
            "User does not have an organization and WCASaaSConfiguration.api_key is not set"
        )
        raise WcaKeyNotFound


    from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY
    if provider_name not in REGISTRY:
        logger.error(f"Provider '{provider_name}' is not available amoung: {sorted(REGISTRY.keys())}")
        raise WcaKeyNotFound

    config = apps.get_app_config("ai").get_model_pipeline(MetaData)
    print(config.config.inference_url)
    if config.config.api_key:
        print("At provider level")
        return config.config.api_key

    if (
        settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
        and any(up.is_active for up in user.userplan_set.all())
        and user.organization
        and not user.organization.has_api_key
    ):
        print("Trial key")
        return config.config.one_click_default_api_key


    secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
    try:
        api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
        if api_key is not None:
            print("At org level")
            return api_key["SecretString"]

    except (WcaSecretManagerError, KeyError):
        # if retrieving the API Key from AWS fails, we log an error
        logger.error(f"error retrieving WCA API Key for org_id '{organization_id}'")
        raise

    raise WcaKeyNotFound


def get_model_id(user, provider_name, requested_model_id: Optional[str] = None,) -> str:
    organization_id = user.organization and user.organization.id

    if organization_id is None:
        logger.error(
            "User does not have an organization and WCASaaSConfiguration.api_key is not set"
        )
        raise WcaKeyNotFound

    from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY
    if provider_name not in REGISTRY:
        logger.error(f"Provider '{provider_name}' is not available amoung: {sorted(REGISTRY.keys())}")
        raise WcaKeyNotFound

    config = apps.get_app_config("ai").get_model_pipeline(MetaData)
    print(config.config.inference_url)
    if config.config.model_id:
        print("At provider level")
        return config.config.model_id

    if (
        settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
        and any(up.is_active for up in user.userplan_set.all())
        and user.organization
        and not user.organization.has_model_id
    ):
        print("Trial key")
        return config.config.one_click_default_model_id

    if requested_model_id:
        # requested_model_id defined: i.e. not None, not "", not {} etc.
        # let them use what they ask for
        logger.debug(f"requested_model_id={requested_model_id}")
        return requested_model_id

    secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
    try:
        model_id = secret_manager.get_secret(organization_id, Suffixes.MODEL_ID)
        if model_id is not None:
            print("At org level")
            return model_id["SecretString"]

    except (WcaSecretManagerError, KeyError):
        # if retrieving the Model ID from AWS fails, we log an error
        logger.error(f"error retrieving WCA Model ID for org_id '{organization_id}'")
        raise

    raise WcaModelIdNotFound

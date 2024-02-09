from django.urls import path

from ansible_wisdom.ai.api.wca.api_key_views import (
    WCAApiKeyValidatorView,
    WCAApiKeyView,
)
from ansible_wisdom.ai.api.wca.model_id_views import (
    WCAModelIdValidatorView,
    WCAModelIdView,
)

urlpatterns = [
    path('apikey/', WCAApiKeyView.as_view(), name='wca_api_key'),
    path('modelid/', WCAModelIdView.as_view(), name='wca_model_id'),
    path('apikey/test/', WCAApiKeyValidatorView.as_view(), name='wca_api_key_validator'),
    path('modelid/test/', WCAModelIdValidatorView.as_view(), name='wca_model_id_validator'),
]

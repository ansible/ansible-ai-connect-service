from ai.api.wca.api_key_views import WCAApiKeyValidatorView, WCAApiKeyView
from ai.api.wca.model_id_views import WCAModelIdValidatorView, WCAModelIdView
from django.urls import path

urlpatterns = [
    path('apikey/', WCAApiKeyView.as_view(), name='wca_api_key'),
    path('modelid/', WCAModelIdView.as_view(), name='wca_model_id'),
    path('apikey/test/', WCAApiKeyValidatorView.as_view(), name='wca_api_key_validator'),
    path('modelid/test/', WCAModelIdValidatorView.as_view(), name='wca_model_id_validator'),
]

from ai.api.wca.api_key_views import WCAApiKeyView
from ai.api.wca.model_id_views import WCAModelIdView
from django.urls import path

urlpatterns = [
    path('apikey/', WCAApiKeyView.as_view(), name='wca_api_key'),
    path('modelid/', WCAModelIdView.as_view(), name='wca_model_id'),
]

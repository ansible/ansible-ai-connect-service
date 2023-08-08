from django.urls import path
from wca.views import WCAKeyDeleteView, WCAKeyListOrCreateView

urlpatterns = [
    path('<str:org_id>/', WCAKeyListOrCreateView.as_view(), name='wca-get-create'),
    path('<str:org_id>/<str:wca_key>', WCAKeyDeleteView.as_view(), name='wca-delete'),
]

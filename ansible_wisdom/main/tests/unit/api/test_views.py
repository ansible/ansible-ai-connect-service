import pytest
from ai.apps import AIConfig
from django.apps import apps
from django.test import Client
from rest_framework.response import Response


class TestAICompletions:
    @pytest.mark.django_db
    def test_basic_completion(
        self, client, mocker, admin_token, basic_infer_prompt, basic_prediction_reply
    ):
        class DummyMeshClient:
            def infer(self, data, model_name=None):
                return Response(basic_prediction_reply)

        rclient = mocker.patch.object(AIConfig, 'retrieve_client', return_value=DummyMeshClient())
        r = client.post(
            '/api/ai/completions/',
            basic_infer_prompt,
            HTTP_AUTHORIZATION=f'Bearer {admin_token.key}',
        )
        assert r.status_code == 200
        assert r.data == basic_prediction_reply
        rclient.assert_called_with(None)

    @pytest.mark.django_db
    def test_get_alternative_model(
        self, client, mocker, admin_token, basic_infer_prompt, basic_prediction_reply, test_ai_model
    ):
        class DummyMeshClient:
            def infer(self, data, model_name=None):
                return Response(basic_prediction_reply)

        rclient = mocker.patch.object(AIConfig, 'retrieve_client', return_value=DummyMeshClient())
        r = client.post(
            '/api/ai/completions/?model_name=test',
            basic_infer_prompt,
            HTTP_AUTHORIZATION=f'Bearer {admin_token.key}',
        )
        rclient.assert_called_with("test")

    @pytest.mark.django_db
    def test_rate_limit(
        self, client, mocker, admin_token, basic_infer_prompt, basic_prediction_reply
    ):
        class DummyMeshClient:
            def infer(self, data, model_name=None):
                return Response(basic_prediction_reply)

        mocker.patch.object(
            apps.get_app_config("ai"), 'retrieve_client', return_value=DummyMeshClient()
        )
        r = client.post(
            '/api/ai/completions/',
            basic_infer_prompt,
            HTTP_AUTHORIZATION=f'Bearer {admin_token.key}',
        )
        assert r.status_code == 200
        for _ in range(10):
            r = client.post(
                '/api/ai/completions/',
                basic_infer_prompt,
                HTTP_AUTHORIZATION=f'Bearer {admin_token.key}',
            )
        assert r.status_code == 429

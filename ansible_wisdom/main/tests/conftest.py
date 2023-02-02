import pytest
from ai.models import AIModel
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()


@pytest.fixture
def test_ai_model():
    return AIModel.objects.create(
        name="test",
        model_mesh_api_type="http",
        inference_url="http://localhost:8080",
        management_url="http://localhost:8080",
    )


@pytest.fixture
def user():
    def u(name, is_superuser=False):
        try:
            user = User.objects.get(username=name)
        except User.DoesNotExist:
            user = User(username=name, is_superuser=is_superuser)
            user.set_password(name)
            user.save()
        return user

    return u


@pytest.fixture
def admin(user):
    return user('admin', True)


@pytest.fixture
def admin_token(admin):
    return Token.objects.get_or_create(user=admin)[0]


@pytest.fixture
def basic_infer_prompt():
    return {"prompt": "foo", "context": "bar"}


@pytest.fixture
def basic_prediction_reply():
    return "{'predictions': [ ['  shell: \"{{ item }}\"\n]}"

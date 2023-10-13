from http import HTTPStatus
from unittest.mock import patch

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.model_client.exceptions import WcaTokenFailure
from ai.api.model_client.wca_client import WCAClient
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.urls import resolve, reverse
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAApiKeyView(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        self.wca_client_patcher = patch.object(
            apps.get_app_config('ai'), 'wca_client', spec=WCAClient
        )
        self.mock_wca_client = self.wca_client_patcher.start()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.wca_client_patcher.stop()
        self.secret_manager_patcher.stop()

    def test_get_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_permission_classes(self, *args):
        url = reverse('wca_api_key')
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            AcceptedTermsPermission,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    def test_get_key_when_undefined(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.API_KEY)

    def test_get_key_when_defined(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        date_time = timezone.now().isoformat()
        self.mock_secret_manager.get_secret.return_value = {'CreatedDate': date_time}
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data['last_update'], date_time)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.API_KEY)

    def test_get_key_when_defined_throws_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.side_effect = WcaSecretManagerError('Test')
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_set_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_set_key_with_valid_value(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.API_KEY)

        # Set Key
        self.mock_wca_client.get_token.return_value = "token"
        with self.assertLogs(logger='users.signals', level='DEBUG') as log:
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "key": "a-new-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            self.mock_secret_manager.save_secret.assert_called_with(
                '123', Suffixes.API_KEY, 'a-new-key'
            )

            # Check Key was stored
            self.mock_secret_manager.get_secret.return_value = {
                'CreatedDate': timezone.now().isoformat()
            }
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.API_KEY)

            # Check audit entry
            self.assertInLog(
                f"User: '{self.user}' set WCA Key for Organisation '{self.user.organization_id}'",
                log,
            )

    def test_set_key_with_invalid_value(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.API_KEY)

        # Set Key
        self.mock_wca_client.get_token.side_effect = WcaTokenFailure('Something went wrong')
        r = self.client.post(
            reverse('wca_api_key'),
            data='{ "key": "a-new-key" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
        self.mock_secret_manager.save_secret.assert_not_called()

    def test_set_key_throws_secret_manager_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.get_token.return_value = "token"
        self.mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
        r = self.client.post(
            reverse('wca_api_key'),
            data='{ "key": "a-new-key" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_set_key_throws_wca_client_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.get_token.side_effect = WcaTokenFailure()
        r = self.client.post(
            reverse('wca_api_key'),
            data='{ "key": "a-new-key" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_set_key_throws_validation_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse('wca_api_key'),
            data='{ "unknown_json_field": "a-new-key" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestWCAApiKeyViewAsNonSubscriber(WisdomServiceAPITestCaseBase):
    def test_get_api_key_as_non_subscriber(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAApiKeyValidatorView(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        self.wca_client_patcher = patch.object(
            apps.get_app_config('ai'), 'wca_client', spec=WCAClient
        )
        self.mock_wca_client = self.wca_client_patcher.start()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.wca_client_patcher.stop()
        self.secret_manager_patcher.stop()

    def test_validate_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_validate_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_validate_key_with_valid_value(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        self.mock_wca_client.get_token.return_value = "token"
        self.mock_wca_client.get_api_key.return_value = "wca_key"
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_validate_key_with_invalid_value(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        self.mock_wca_client.get_token.side_effect = WcaTokenFailure('Something went wrong')
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

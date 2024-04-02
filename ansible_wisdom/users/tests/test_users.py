import random
import string
from http import HTTPStatus
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock, patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from prometheus_client.parser import text_string_to_metric_families
from social_core.exceptions import AuthCanceled
from social_django.models import UserSocialAuth

import ansible_wisdom.ai.feature_flags as feature_flags
from ansible_wisdom.ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_wisdom.ai.api.tests.test_views import APITransactionTestCase
from ansible_wisdom.organizations.models import Organization
from ansible_wisdom.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
)
from ansible_wisdom.users.auth import BearerTokenAuthentication
from ansible_wisdom.users.constants import (
    FAUX_COMMERCIAL_USER_ORG_ID,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_wisdom.users.pipeline import _terms_of_service
from ansible_wisdom.users.views import TermsOfService


def create_user(
    username: str = None,
    password: str = None,
    provider: str = None,
    social_auth_extra_data: any = {},
    external_username: str = "",
    rh_user_is_org_admin: Optional[bool] = None,
    rh_user_id: str = None,
    rh_org_id: int = 1234567,
    org_opt_out: bool = False,
):
    (org, _) = Organization.objects.get_or_create(id=rh_org_id, _telemetry_opt_out=org_opt_out)
    username = username or 'u' + "".join(random.choices(string.digits, k=5))
    password = password or 'secret'
    email = username + '@example.com'
    user = get_user_model().objects.create_user(
        username=username,
        email=email,
        password=password,
        organization=org if provider == USER_SOCIAL_AUTH_PROVIDER_OIDC else None,
    )
    if provider:
        rh_user_id = rh_user_id or str(uuid4())
        user.external_username = external_username or username
        social_auth = UserSocialAuth.objects.create(user=user, provider=provider, uid=rh_user_id)
        social_auth.set_extra_data(social_auth_extra_data)
        if rh_user_is_org_admin:
            user.rh_user_is_org_admin = rh_user_is_org_admin
    user.save()
    return user


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestUsers(APITransactionTestCase, WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.password = "somepassword"
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username="anexternalusername",
        )
        cache.clear()

    def test_users(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(self.user.username, r.data.get('username'))

    def test_home_view(self):
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn(self.user.external_username, str(r.content))

    def test_home_view_without_login(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn('You are currently not logged in.', str(r.content))

    def test_auth_keyword(self):
        bearer = BearerTokenAuthentication()
        self.assertEqual(bearer.keyword, "Bearer")

    def test_users_audit_logging(self):
        with self.assertLogs(logger='ansible_wisdom.users.signals', level='INFO') as log:
            self.client.login(username=self.user.username, password=self.password)
            self.assertInLog('LOGIN successful', log)


@override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
class TestTermsAndConditions(WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
        super().setUp()

        class MockSession(dict):
            def save(self):
                pass

        class MockRequest:
            GET = {}
            POST = {}

            def __init__(self):
                self.session = MockSession()

        class MockBackend:
            name = 'github'

        class MockStrategy:
            session = None
            redirect_url = None

            def redirect(self, redirect_url):
                self.redirect_url = redirect_url

            def partial_load(self, partial_token):
                if partial_token == 'invalid_token':
                    return None
                else:
                    return SimpleNamespace(backend='backend', token=partial_token)

            def session_get(self, key, default=None):
                return self.session.get(key, default)

        # class MockUser:
        #     community_terms_accepted = None
        #     saved = False

        #     def save(self):
        #         self.saved = True

        self.request = MockRequest()
        self.backend = MockBackend()
        self.strategy = MockStrategy()
        self.strategy.session = self.request.session
        self.partial = SimpleNamespace(token='token')
        self.user = Mock(
            community_terms_accepted=None, commercial_terms_accepted=None, rh_user_has_seat=False
        )
        cache.clear()

    def test_terms_of_service_community_first_call(self):
        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertIsNone(self.request.session.get('terms_accepted', None))
        self.assertEqual(self.strategy.redirect_url, '/community-terms/?partial_token=token')
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)

    def test_terms_of_service_first_commercial(self):
        # We must be using the Red Hat SSO and be a member of the Community placeholder group
        # Commercial Users enclosed Terms of Service by default earlier, no need to ask them again
        self.backend.name = 'oidc'
        self.user.rh_user_has_seat = True

        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertIsNone(self.request.session.get('terms_accepted', None))
        self.assertNotEqual(self.strategy.redirect_url, '/community-terms/?partial_token=token')
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)

    def test_terms_of_service_commercial_previously_accepted(self):
        now = timezone.now()
        self.user.community_terms_accepted = now
        self.backend.name = 'oidc'
        self.user.rh_user_has_seat = True
        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )

        self.assertNotEqual(self.strategy.redirect_url, '/community-terms/?partial_token=token')
        self.assertFalse(self.user.save.called)
        self.assertEqual(self.user.community_terms_accepted, now)

    def test_terms_of_service_community_previously_accepted(self):
        now = timezone.now()
        self.user.community_terms_accepted = now
        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )

        self.assertNotEqual(self.strategy.redirect_url, '/community-terms/?partial_token=token')
        self.assertFalse(self.user.save.called)
        self.assertEqual(self.user.community_terms_accepted, now)

    def test_terms_of_service_with_acceptance(self):
        self.request.session['terms_accepted'] = True
        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertTrue(self.user.save.called)
        self.assertIsNotNone(self.user.community_terms_accepted)

    def test_terms_of_service_without_acceptance(self):
        self.request.session['terms_accepted'] = False
        with self.assertRaises(AuthCanceled):
            _terms_of_service(
                self.strategy,
                self.user,
                self.backend,
                request=self.request,
                current_partial=self.partial,
            )
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)

    @override_settings(TERMS_NOT_APPLICABLE=True)
    def test_terms_of_service_with_override(self):
        self.request.session['terms_accepted'] = False
        result = _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertEqual(result, {'terms_accepted': True})
        self.assertIsNone(self.strategy.redirect_url)
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_terms_of_service_after_tech_preview(self):
        self.request.session['terms_accepted'] = False
        result = _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertEqual(result, {'terms_accepted': True})
        self.assertIsNone(self.strategy.redirect_url)
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)

    @patch('social_django.utils.get_strategy')
    def test_post_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'True'
        view = TermsOfService(template_name='users/community-terms.html')
        view.post(self.request)
        self.assertTrue(self.request.session['terms_accepted'])
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    @patch('social_django.utils.get_strategy')
    def test_post_not_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService(template_name='users/community-terms.html')
        view.post(self.request)
        self.assertFalse(self.request.session['terms_accepted'])
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    @patch('social_django.utils.get_strategy')
    def test_post_without_partial_token(self, get_strategy):
        get_strategy.return_value = self.strategy
        # self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService(template_name='users/community-terms.html')
        with self.assertLogs(logger='root', level='WARN') as log:
            res = view.post(self.request)
            self.assertEqual(400, res.status_code)
            self.assertInLog('POST TermsOfService was invoked without partial_token', log)

    @patch('social_django.utils.get_strategy')
    def test_post_with_invalid_partial_token(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.POST['partial_token'] = 'invalid_token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService(template_name='users/community-terms.html')
        with self.assertLogs(logger='root', level='ERROR') as log:
            res = view.post(self.request)
            self.assertEqual(400, res.status_code)
            self.assertInLog('strategy.partial_load(partial_token) returned None', log)

    def test_get(self):
        view = TermsOfService(template_name='users/community-terms.html')
        setattr(view, 'request', self.request)  # needed for TemplateResponseMixin
        self.request.GET['partial_token'] = 'token'
        res = view.get(self.request)
        self.assertEqual(200, res.status_code)
        self.assertIn('form', res.context_data)
        self.assertIn('partial_token', res.context_data)

    def test_get_without_partial_token(self):
        view = TermsOfService(template_name='users/community-terms.html')
        setattr(view, 'request', self.request)  # needed for TemplateResponseMixin
        # self.request.GET['partial_token'] = 'token'
        with self.assertLogs(logger='root', level='WARN') as log:
            res = view.get(self.request)
            self.assertEqual(403, res.status_code)
            self.assertInLog('GET TermsOfService was invoked without partial_token', log)


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS='1981:valid')
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_USERS_WITH_SEAT="seated")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="1981")
class TestUserSeat(WisdomAppsBackendMocking):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_rh_user_has_seat_with_no_rhsso_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.assertFalse(user.rh_user_has_seat)

    def test_rh_user_has_seat_with_rhsso_user_no_seat(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, username="not-seated")
        self.assertFalse(user.rh_user_has_seat)

    def test_rh_user_has_seat_with_rhsso_user_with_seat(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="seated",
        )
        self.assertTrue(user.rh_user_has_seat)

    def test_rh_user_has_seat_with_no_seat_checker(self):
        with patch.object(apps.get_app_config('ai'), 'get_seat_checker', lambda: None):
            user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
            self.assertFalse(user.rh_user_has_seat)

    def test_rh_user_in_unlimited_org(self):
        with patch.object(apps.get_app_config('ai'), 'get_seat_checker', lambda: None):
            user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
            org = Organization(None, None)
            org.is_subscription_check_should_be_bypassed = True
            user.organization = org
            self.assertTrue(user.rh_org_has_subscription)

    def test_rh_user_has_seat_with_github_commercial_group(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)

        commercial_group, _ = Group.objects.get_or_create(name='Commercial')
        user.groups.add(commercial_group)

        self.assertTrue(user.rh_user_has_seat)
        self.assertEqual(user.org_id, FAUX_COMMERCIAL_USER_ORG_ID)

    def test_rh_user_has_seat_with_rhsso_commercial_group(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)

        commercial_group, _ = Group.objects.get_or_create(name='Commercial')
        user.groups.add(commercial_group)

        self.assertTrue(user.rh_user_has_seat)
        self.assertEqual(user.org_id, FAUX_COMMERCIAL_USER_ORG_ID)

    def test_rh_user_org_with_sub_but_no_seat_in_ams(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertTrue(user.rh_user_has_seat)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
    def test_rh_user_org_with_sub_but_no_sec_and_tech_preview(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertFalse(user.rh_user_has_seat)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
    def test_rh_user_org_with_sub_but_no_sec_after_tech_preview(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertTrue(user.rh_user_has_seat)


class TestUsername(WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.local_user = create_user(
            username="local-user",
            password="bar",
        )

        self.sso_user = create_user(
            username="sso-user",
            password="bar",
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username="babar",
        )
        cache.clear()

    def tearDown(self) -> None:
        self.local_user.delete()
        self.sso_user.delete()
        super().tearDown()

    def test_username_from_sso(self) -> None:
        self.assertEqual(self.sso_user.external_username, "babar")
        self.assertEqual(self.local_user.external_username, "")


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="1981")
class TestIsOrgLightspeedSubscriber(WisdomAppsBackendMocking):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_rh_org_has_subscription_with_no_rhsso_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.assertFalse(user.rh_org_has_subscription)

    def test_rh_org_has_subscription_with_subscribed_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, rh_org_id=1981)
        self.assertTrue(user.rh_org_has_subscription)

    def test_rh_org_has_subscription_with_non_subscribed_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.assertFalse(user.rh_org_has_subscription)


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestThirdPartyAuthentication(WisdomAppsBackendMocking, APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_github_user_external_username(self):
        external_username = "github_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username=external_username,
        )
        self.assertEqual(external_username, user.external_username)
        self.assertNotEqual(user.username, user.external_username)
        self.assertNotEqual(user.external_username, "")

    def test_rhsso_user_external_username(self):
        external_username = "sso_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )
        self.assertEqual(external_username, user.external_username)
        self.assertNotEqual(user.username, user.external_username)
        self.assertNotEqual(user.external_username, "")

    def test_github_user_login(self):
        external_username = "github_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username=external_username,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(external_username, r.data.get('external_username'))
        self.assertNotEqual(user.username, r.data.get('external_username'))

    def test_rhsso_user_login(self):
        external_username = "sso_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(external_username, r.data.get('external_username'))
        self.assertNotEqual(user.username, r.data.get('external_username'))

    def test_user_login_with_same_usernames(self):
        external_username = "a_username"
        oidc_user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )

        github_user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB, external_username=external_username
        )

        self.client.force_authenticate(user=oidc_user)
        r = self.client.get(reverse('me'))
        self.assertEqual(external_username, r.data.get('external_username'))

        self.client.force_authenticate(user=github_user)
        r = self.client.get(reverse('me'))
        self.assertEqual(external_username, r.data.get('external_username'))

        self.assertNotEqual(oidc_user.username, github_user.username)
        self.assertEqual(oidc_user.external_username, github_user.external_username)


class TestUserModelMetrics(APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_user_model_metrics(self):
        def get_user_count():
            r = self.client.get(reverse('prometheus-django-metrics'))
            for family in text_string_to_metric_families(r.content.decode()):
                for sample in family.samples:
                    if sample[0] == 'django_model_inserts_total' and sample[1] == {'model': 'user'}:
                        return sample[2]

        # Obtain the user count before creating a dummy user
        before = get_user_count()

        # Create a dummy user
        username = 'u' + "".join(random.choices(string.digits, k=5))
        password = 'secret'
        email = username + '@example.com'
        get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        # Make sure that the user count incremented
        self.assertEqual(1, get_user_count() - before)


class TestTelemetryOptInOut(APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        feature_flags.FeatureFlags.instance = None

    def test_github_user(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            social_auth_extra_data={"login": "github_username"},
            external_username="github_username",
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNone(r.data.get('org_telemetry_opt_out'))

    def test_rhsso_user_with_telemetry_opted_in(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
            org_opt_out=False,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get('org_telemetry_opt_out'))

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_rhsso_user_with_telemetry_opted_out(self, LDClient):
        LDClient.return_value.variation.return_value = True
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
            org_opt_out=True,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get('org_telemetry_opt_out'))

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    @patch.object(AcceptedTermsPermission, 'has_permission', return_value=True)
    @patch.object(feature_flags, 'LDClient')
    def test_rhsso_user_caching(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
        )
        self.client.force_authenticate(user=user)

        # Default is False
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get('org_telemetry_opt_out'))

        # Update to True
        r = self.client.post(
            reverse('telemetry_settings'),
            data='{ "optOut": "True" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

        # Cached value should persist
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get('org_telemetry_opt_out'))

        # Emulate cache expiring
        cache.clear()

        # Cache should update
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get('org_telemetry_opt_out'))

import random
import string
from http import HTTPStatus
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from ai.api.tests.test_views import APITransactionTestCase, WisdomServiceAPITestCaseBase
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from prometheus_client.parser import text_string_to_metric_families
from social_core.exceptions import AuthCanceled
from social_django.models import UserSocialAuth
from test_utils import WisdomServiceLogAwareTestCase
from users.auth import BearerTokenAuthentication
from users.pipeline import _terms_of_service
from users.views import TermsOfService


def create_user(provider_name: str):
    username = 'u' + "".join(random.choices(string.digits, k=5))
    password = 'secret'
    email = username + '@example.com'
    user = get_user_model().objects.create_user(
        username=username,
        email=email,
        password=password,
    )
    UserSocialAuth.objects.create(user=user, provider=provider_name, uid=str(uuid4()))
    return user


class TestUsers(WisdomServiceAPITestCaseBase):
    def test_users(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(self.username, r.data.get('username'))

    def test_home_view(self):
        self.login()
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn(self.username, str(r.content))

    def test_home_view_without_login(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn('You are currently not logged in.', str(r.content))

    def test_auth_keyword(self):
        bearer = BearerTokenAuthentication()
        self.assertEqual(bearer.keyword, "Bearer")


class TestTermsAndConditions(WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
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
        #     commercial_terms_accepted = None
        #     saved = False

        #     def save(self):
        #         self.saved = True

        self.request = MockRequest()
        self.backend = MockBackend()
        self.strategy = MockStrategy()
        self.strategy.session = self.request.session
        self.partial = SimpleNamespace(token='token')
        self.user = Mock(community_terms_accepted=None, commercial_terms_accepted=None)
        self.group_filter = self.user.groups.filter(name='Commercial')
        self.group_filter.exists.return_value = False

    def test_terms_of_service_first_call(self):
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
        self.assertIsNone(self.user.commercial_terms_accepted)

    def test_terms_of_service_first_commercial(self):
        # We must be using the Red Hat SSO and be a member of the Community placeholder group
        self.backend.name = 'oidc'
        self.group_filter.exists.return_value = True

        _terms_of_service(
            self.strategy,
            self.user,
            self.backend,
            request=self.request,
            current_partial=self.partial,
        )
        self.assertIsNone(self.request.session.get('terms_accepted', None))
        self.assertEqual(self.strategy.redirect_url, '/commercial-terms/?partial_token=token')
        self.assertFalse(self.user.save.called)
        self.assertIsNone(self.user.community_terms_accepted)
        self.assertIsNone(self.user.commercial_terms_accepted)

    def test_terms_of_service_previously_accepted(self):
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
        self.assertIsNone(self.user.commercial_terms_accepted)

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
        self.assertIsNone(self.user.commercial_terms_accepted)

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


class TestUserSeat(TestCase):
    def test_has_seat_with_no_rhsso_user(self):
        user = create_user(provider_name="github")
        self.assertFalse(user.has_seat)

    @override_settings(AUTHZ_BACKEND_TYPE="mock_false")
    def test_has_seat_with_rhsso_user_no_seat(self):
        user = create_user(provider_name="oidc")
        self.assertFalse(user.has_seat)

    @override_settings(AUTHZ_BACKEND_TYPE="mock_true")
    def test_has_seat_with_rhsso_user_with_seat(self):
        user = create_user(provider_name="oidc")
        self.assertTrue(user.has_seat)

    def test_has_seat_with_no_seat_checker(self):
        with patch.object(apps.get_app_config('ai'), 'get_seat_checker', lambda: None):
            user = create_user(provider_name="oidc")
            self.assertFalse(user.has_seat)


class TestOrgAdmin(TestCase):
    def test_is_org_admin_with_no_rhsso_user(self):
        user = create_user(provider_name="github")
        self.assertFalse(user.is_org_admin)

    @override_settings(AUTHZ_BACKEND_TYPE="mock_true")
    def test_is_org_admin_with_admin_rhsso_user(self):
        user = create_user(provider_name="oidc")
        self.assertTrue(user.is_org_admin)

    @override_settings(AUTHZ_BACKEND_TYPE="mock_false")
    def test_is_org_admin_with_non_admin_rhsso_user(self):
        user = create_user(provider_name="oidc")
        self.assertFalse(user.is_org_admin)


class TestUserModelMetrics(APITransactionTestCase):
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

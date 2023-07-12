import random
import string
from datetime import datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai.api.tests.test_views import APITransactionTestCase, WisdomServiceAPITestCaseBase
from django.contrib.auth import get_user_model
from django.urls import reverse
from prometheus_client.parser import text_string_to_metric_families
from social_core.exceptions import AuthCanceled
from users.pipeline import _add_date_accepted, _terms_of_service
from users.views import TermsOfService


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


class TestTermsAndConditions(TestCase):
    def setUp(self) -> None:
        class MockSession(dict):
            def save(self):
                pass

        class MockRequest:
            GET = {}
            POST = {}

            def __init__(self):
                self.session = MockSession()

        class MockStrategy:
            def redirect(self, redirect_url):
                self.redirect_url = redirect_url

            def partial_load(self, partial_token):
                if partial_token == 'invalid_token':
                    return None
                else:
                    return SimpleNamespace(backend='backend', token=partial_token)

        class MockUser:
            date_terms_accepted = None
            saved = False

            def save(self):
                self.saved = True

        self.request = MockRequest()
        self.strategy = MockStrategy()
        self.partial = SimpleNamespace(token='token')
        self.user = MockUser()

    def searchInLogOutput(self, s, logs):
        for log in logs:
            if s in log:
                return True
        return False

    def assertInLog(self, s, logs):
        self.assertTrue(self.searchInLogOutput(s, logs), logs)

    def test_terms_of_service_first_call(self):
        _terms_of_service(
            self.strategy, self.user, request=self.request, current_partial=self.partial
        )
        self.assertEqual(datetime.max.timestamp(), self.request.session['ts_date_terms_accepted'])
        self.assertEqual('/terms_of_service/?partial_token=token', self.strategy.redirect_url)

    def test_terms_of_service_with_acceptance(self):
        now = datetime.utcnow().timestamp()
        self.request.session['ts_date_terms_accepted'] = now
        _terms_of_service(
            self.strategy, self.user, request=self.request, current_partial=self.partial
        )
        self.assertEqual(now, self.request.session['ts_date_terms_accepted'])

    def test_terms_of_service_without_acceptance(self):
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        with self.assertRaises(AuthCanceled):
            _terms_of_service(
                self.strategy, self.user, request=self.request, current_partial=self.partial
            )

    def test_add_date_accepted_with_date_accepted(self):
        now = datetime.utcnow().timestamp()
        self.request.session['ts_date_terms_accepted'] = now
        _add_date_accepted(self.strategy, self.user, request=self.request)
        self.assertTrue(self.user.saved)
        self.assertEqual(now, self.user.date_terms_accepted.timestamp())

    def test_add_date_accepted_without_date_accepted(self):
        _add_date_accepted(self.strategy, self.user, request=self.request)
        self.assertFalse(self.user.saved)
        self.assertIsNone(self.user.date_terms_accepted)

    @patch('social_django.utils.get_strategy')
    def test_post_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'True'
        view = TermsOfService()
        view.post(self.request)
        self.assertNotEqual(
            datetime.max.timestamp(), self.request.session['ts_date_terms_accepted']
        )
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    @patch('social_django.utils.get_strategy')
    def test_post_not_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService()
        view.post(self.request)
        self.assertEqual(datetime.max.timestamp(), self.request.session['ts_date_terms_accepted'])
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    @patch('social_django.utils.get_strategy')
    def test_post_without_partial_token(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['date_terms_accepted'] = datetime.max
        # self.request.POST['partial_token'] = 'token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService()
        with self.assertLogs(logger='root', level='ERROR') as log:
            res = view.post(self.request)
            self.assertEqual(400, res.status_code)
            self.assertInLog(
                'POST /terms_of_service/ was invoked without partial_token', log.output
            )

    @patch('social_django.utils.get_strategy')
    def test_post_with_invalid_partial_token(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        self.request.POST['partial_token'] = 'invalid_token'
        self.request.POST['accepted'] = 'False'
        view = TermsOfService()
        with self.assertLogs(logger='root', level='ERROR') as log:
            res = view.post(self.request)
            self.assertEqual(400, res.status_code)
            self.assertInLog('strategy.partial_load(partial_token) returned None', log.output)

    def test_get(self):
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        view = TermsOfService()
        setattr(view, 'request', self.request)  # needed for TemplateResponseMixin
        self.request.GET['partial_token'] = 'token'
        res = view.get(self.request)
        self.assertEqual(200, res.status_code)
        self.assertIn('form', res.context_data)
        self.assertIn('partial_token', res.context_data)

    def test_get_without_partial_token(self):
        self.request.session['ts_date_terms_accepted'] = datetime.max.timestamp()
        view = TermsOfService()
        setattr(view, 'request', self.request)  # needed for TemplateResponseMixin
        # self.request.GET['partial_token'] = 'token'
        with self.assertLogs(logger='root', level='ERROR') as log:
            res = view.get(self.request)
            self.assertEqual(403, res.status_code)
            self.assertInLog('GET /terms_of_service/ was invoked without partial_token', log.output)


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

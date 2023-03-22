from datetime import datetime
from functools import wraps
from http import HTTPStatus
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.urls import reverse
from social_core.exceptions import AuthCanceled
from users.views import TermsOfService, _add_date_accepted, _terms_of_service


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
        self.assertIn(f'You are signed in as {self.username}.', str(r.content))

    def test_home_view_without_login(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn('You are not signed in.', str(r.content))


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

            def partial_load(self, parial_token):
                return SimpleNamespace(backend='backend', token='token')

        class MockUser:
            date_terms_accepted = None
            saved = False

            def save(self):
                self.saved = True

        self.request = MockRequest()
        self.strategy = MockStrategy()
        self.partial = SimpleNamespace(token='token')
        self.user = MockUser()

    def test_terms_of_service_first_call(self):
        _terms_of_service(self.strategy, request=self.request, current_partial=self.partial)
        self.assertEqual(datetime.max, self.request.session['date_terms_accepted'])
        self.assertEqual('/terms_of_service/?partial_token=token', self.strategy.redirect_url)

    def test_terms_of_service_with_acceptance(self):
        now = datetime.now()
        self.request.session['date_terms_accepted'] = now
        _terms_of_service(self.strategy, request=self.request, current_partial=self.partial)
        self.assertEqual(now, self.request.session['date_terms_accepted'])

    def test_terms_of_service_without_acceptance(self):
        self.request.session['date_terms_accepted'] = datetime.max
        with self.assertRaises(AuthCanceled):
            _terms_of_service(self.strategy, request=self.request, current_partial=self.partial)

    def test_add_date_accepted_with_date_accepted(self):
        now = datetime.now()
        self.request.session['date_terms_accepted'] = now
        _add_date_accepted(self.strategy, self.user, request=self.request)
        self.assertTrue(self.user.saved)
        self.assertEqual(now, self.user.date_terms_accepted)

    def test_add_date_accepted_without_date_accepted(self):
        _add_date_accepted(self.strategy, self.user, request=self.request)
        self.assertFalse(self.user.saved)
        self.assertIsNone(self.user.date_terms_accepted)

    @patch('social_django.utils.get_strategy')
    def test_post_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['date_terms_accepted'] = datetime.max
        self.request.POST['accepted'] = 'True'
        view = TermsOfService()
        view.post(self.request)
        self.assertNotEqual(datetime.max, self.request.session['date_terms_accepted'])
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    @patch('social_django.utils.get_strategy')
    def test_post_not_accepted(self, get_strategy):
        get_strategy.return_value = self.strategy
        self.request.session['date_terms_accepted'] = datetime.max
        self.request.POST['accepted'] = 'False'
        view = TermsOfService()
        view.post(self.request)
        self.assertEqual(datetime.max, self.request.session['date_terms_accepted'])
        self.assertEqual('/complete/backend/?partial_token=token', self.strategy.redirect_url)

    def test_get(self):
        self.request.session['date_terms_accepted'] = datetime.max
        view = TermsOfService()
        setattr(view, 'request', self.request)  # needed for TemplateResponseMixin
        res = view.get(self.request)
        self.assertEqual(200, res.status_code)
        self.assertIn('form', res.context_data)
        self.assertIn('partial_token', res.context_data)

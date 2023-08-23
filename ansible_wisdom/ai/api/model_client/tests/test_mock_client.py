from unittest import TestCase, mock

import requests
from django.test import SimpleTestCase, override_settings

from ..mock_client import MockClient

latency = 300
body = {"test": "true"}
random_value = 10


@override_settings(MOCK_MODEL_RESPONSE_MAX_LATENCY_MSEC=latency)
@override_settings(MOCK_MODEL_RESPONSE_BODY=body)
class TestMockClient(SimpleTestCase):
    def test_init(self):
        url = "https://redhat.com"
        session = requests.Session()
        with mock.patch("requests.Session", return_value=session):
            client = MockClient(inference_url=url)
            self.assertEqual(client._inference_url, url)
            self.assertEqual(client.session, session)
            self.assertEqual(client.headers["Content-Type"], "application/json")

    @override_settings(MOCK_MODEL_RESPONSE_LATENCY_USE_JITTER=True)
    @mock.patch("time.sleep")
    @mock.patch("random.random")
    @mock.patch("json.loads")
    def test_infer_with_jitter(self, loads, random, sleep):
        client = MockClient(inference_url="https://example.com")
        random.return_value = random_value
        client.infer(model_input="input")
        sleep.assert_called_once_with((latency * random_value) / 1000)
        loads.assert_called_once_with(body)

    @override_settings(MOCK_MODEL_RESPONSE_LATENCY_USE_JITTER=False)
    @mock.patch("time.sleep")
    @mock.patch("json.loads")
    def test_infer_without_jitter(self, loads, sleep):
        client = MockClient(inference_url="https://ibm.com")
        client.infer(model_input="input")
        sleep.assert_called_once_with(latency / 1000)
        loads.assert_called_once_with(body)

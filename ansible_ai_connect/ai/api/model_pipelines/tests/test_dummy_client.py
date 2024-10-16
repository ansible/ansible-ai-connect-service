#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from unittest import mock
from unittest.mock import Mock

import requests
from django.test import SimpleTestCase, override_settings

from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
    DummyCompletionsPipeline,
    DummyMetaData,
    DummyPlaybookExplanationPipeline,
    DummyPlaybookGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
)

latency = 3000
body = {"test": "true"}
random_value = 1000


@override_settings(DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC=latency)
@override_settings(DUMMY_MODEL_RESPONSE_BODY=body)
class TestDummyClient(SimpleTestCase):
    def test_init(self):
        url = "https://redhat.com"
        session = requests.Session()
        with mock.patch("requests.Session", return_value=session):
            client = DummyMetaData(inference_url=url)
            self.assertEqual(client._inference_url, url)
            self.assertEqual(client.session, session)
            self.assertEqual(client.headers["Content-Type"], "application/json")

    @override_settings(MOCK_MODEL_RESPONSE_LATENCY_USE_JITTER=True)
    @mock.patch("time.sleep")
    @mock.patch("secrets.randbelow")
    @mock.patch("json.loads")
    def test_infer_with_jitter(self, loads, randbelow, sleep):
        client = DummyCompletionsPipeline(inference_url="https://example.com")
        randbelow.return_value = random_value
        client.invoke(CompletionsParameters.init(Mock(), model_input={"input": "input"}))
        sleep.assert_called_once_with(latency / 1000)
        loads.assert_called_once_with(body)

    @override_settings(MOCK_MODEL_RESPONSE_LATENCY_USE_JITTER=False)
    @mock.patch("time.sleep")
    @mock.patch("json.loads")
    def test_infer_without_jitter(self, loads, sleep):
        client = DummyCompletionsPipeline(inference_url="https://ibm.com")
        client.invoke(CompletionsParameters.init(Mock(), model_input={"input": "input"}))
        sleep.assert_called_once_with(latency / 1000)
        loads.assert_called_once_with(body)

    def test_generate_playbook(self):
        client = DummyPlaybookGenerationPipeline(inference_url="https://ibm.com")
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(request=Mock(), text="foo", create_outline=False)
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertEqual(outline, "")

    def test_generate_playbook_with_outline(self):
        client = DummyPlaybookGenerationPipeline(inference_url="https://ibm.com")
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(request=Mock(), text="foo", create_outline=True)
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertTrue(outline)

    def test_generate_playbook_with_model_id(self):
        client = DummyPlaybookGenerationPipeline(inference_url="https://ibm.com")
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(
                request=Mock(), text="foo", create_outline=True, model_id="mymodel"
            )
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertTrue(outline)

    def test_explain_playbook(self):
        client = DummyPlaybookExplanationPipeline(inference_url="https://ibm.com")
        explanation = client.invoke(PlaybookExplanationParameters.init(Mock(), "ëoo"))
        self.assertTrue(isinstance(explanation, str))
        self.assertTrue(explanation)

    def test_explain_playbook_with_model_id(self):
        client = DummyPlaybookExplanationPipeline(inference_url="https://ibm.com")
        explanation = client.invoke(
            PlaybookExplanationParameters.init(Mock(), "ëoo", model_id="mymodel")
        )
        self.assertTrue(isinstance(explanation, str))
        self.assertTrue(explanation)

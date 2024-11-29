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
from django.test import SimpleTestCase

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
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config

latency = 3000
body = {"test": "true"}
random_value = 1000


class TestDummyClient(SimpleTestCase):
    def test_init(self):
        session = requests.Session()
        config = mock_pipeline_config("dummy")
        with mock.patch("requests.Session", return_value=session):
            client = DummyMetaData(config)
            self.assertEqual(client.session, session)
            self.assertEqual(client.headers["Content-Type"], "application/json")

    @mock.patch("time.sleep")
    @mock.patch("secrets.randbelow")
    @mock.patch("json.loads")
    def test_infer_with_jitter(self, loads, randbelow, sleep):
        client = DummyCompletionsPipeline(
            mock_pipeline_config(
                "dummy", latency_use_jitter=True, latency_max_msec=latency / 1000, body=body
            )
        )
        randbelow.return_value = random_value
        client.invoke(CompletionsParameters.init(Mock(), model_input={"input": "input"}))
        sleep.assert_called_once_with(latency / 1000)
        loads.assert_called_once_with(body)

    @mock.patch("time.sleep")
    @mock.patch("json.loads")
    def test_infer_without_jitter(self, loads, sleep):
        client = DummyCompletionsPipeline(
            mock_pipeline_config(
                "dummy", latency_use_jitter=False, latency_max_msec=latency, body=body
            )
        )
        client.invoke(CompletionsParameters.init(Mock(), model_input={"input": "input"}))
        sleep.assert_called_once_with(latency / 1000)
        loads.assert_called_once_with(body)

    def test_generate_playbook(self):
        client = DummyPlaybookGenerationPipeline(mock_pipeline_config("dummy"))
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(request=Mock(), text="foo", create_outline=False)
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertEqual(outline, "")

    def test_generate_playbook_with_outline(self):
        client = DummyPlaybookGenerationPipeline(mock_pipeline_config("dummy"))
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(request=Mock(), text="foo", create_outline=True)
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertTrue(outline)

    def test_generate_playbook_with_model_id(self):
        client = DummyPlaybookGenerationPipeline(mock_pipeline_config("dummy"))
        playbook, outline, warnings = client.invoke(
            PlaybookGenerationParameters.init(
                request=Mock(), text="foo", create_outline=True, model_id="mymodel"
            )
        )
        self.assertTrue(isinstance(playbook, str))
        self.assertTrue(isinstance(outline, str))
        self.assertTrue(outline)

    def test_explain_playbook(self):
        client = DummyPlaybookExplanationPipeline(mock_pipeline_config("dummy"))
        explanation = client.invoke(PlaybookExplanationParameters.init(Mock(), "ëoo"))
        self.assertTrue(isinstance(explanation, str))
        self.assertTrue(explanation)

    def test_explain_playbook_with_model_id(self):
        client = DummyPlaybookExplanationPipeline(mock_pipeline_config("dummy"))
        explanation = client.invoke(
            PlaybookExplanationParameters.init(Mock(), "ëoo", model_id="mymodel")
        )
        self.assertTrue(isinstance(explanation, str))
        self.assertTrue(explanation)

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

from unittest import TestCase, mock

from .schema1 import (
    InlineSuggestionFeedbackEvent,
    IssueFeedbackEvent,
    PlaybookExplanationFeedbackEvent,
    PlaybookGenerationActionEvent,
    Schema1Event,
    SentimentFeedbackEvent,
    SuggestionQualityFeedbackEvent,
)


class TestSchema1Event(TestCase):
    def test_set_user(self):
        m_user = mock.Mock()
        m_user.rh_user_has_seat = True
        m_user.org_id = 123
        m_user.groups.values_list.return_value = ["mecano"]
        event1 = Schema1Event()
        event1.set_user(m_user)
        self.assertEqual(event1.rh_user_has_seat, True)
        self.assertEqual(event1.rh_user_org_id, 123)
        self.assertEqual(event1.groups, ["mecano"])

    def test_as_dict(self):
        event1 = Schema1Event()
        as_dict = event1.as_dict()

        self.assertEqual(as_dict.get("event_name"), None)
        self.assertFalse(as_dict.get("exception"), False)

    def test_set_exception(self):
        event1 = Schema1Event()
        try:
            1 / 0
        except Exception as e:
            event1.set_exception(e)
            self.assertTrue(event1.exception)
            self.assertEqual(event1.response.exception, "division by zero")


class TestInlineSuggestionFeedbackEvent(TestCase):
    def test_validated_data(self):
        validated_data = {
            "inlineSuggestion": {
                "latency": 1.1,
                "userActionTime": 1,
                "action": "123",
                "suggestionId": "1e0e1404-5b8a-4d06-829a-dca0d2fff0b5",
            }
        }
        event1 = InlineSuggestionFeedbackEvent(validated_data)
        self.assertEqual(event1.action, 0)
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.action, 123)


class TestSuggestionQualityFeedbackEvent(TestCase):
    def test_validated_data(self):
        validated_data = {
            "suggestionQualityFeedback": {"prompt": "Yo!", "providedSuggestion": "bateau"}
        }
        event1 = SuggestionQualityFeedbackEvent()
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.providedSuggestion, "bateau")


class TestSentimentFeedbackEvent(TestCase):
    def test_validated_data(self):
        validated_data = {"sentimentFeedback": {"value": "1", "feedback": "C'est beau"}}
        event1 = SentimentFeedbackEvent()
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.value, 1)


class TestIssueFeedbackEvent(TestCase):
    def test_validated_data(self):
        validated_data = {
            "issueFeedback": {"type": "1", "title": "C'est beau", "description": "Et oui!"}
        }
        event1 = IssueFeedbackEvent()
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.title, "C'est beau")


class TestPlaybookExplanationFeedbackEvent(TestCase):
    def test_validated_data(self):
        validated_data = {
            "playbookExplanationFeedback": {
                "action": "1",
                "explanation": "1ddda23c-5f8c-4015-b915-4951b8039ffa",
            }
        }
        event1 = PlaybookExplanationFeedbackEvent()
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.action, 1)


class TestPlaybookGenerationActionEvent(TestCase):
    def test_validated_data(self):
        validated_data = {
            "playbookGenerationAction": {
                "action": "2",
                "from_page": 1,
                "to_page": "2",
                "wizard_id": "1ddda23c-5f8c-4015-b915-4951b8039ffa",
            }
        }
        event1 = PlaybookGenerationActionEvent()
        event1.set_validated_data(validated_data)
        self.assertEqual(event1.action, 2)
        self.assertEqual(event1.to_page, 2)

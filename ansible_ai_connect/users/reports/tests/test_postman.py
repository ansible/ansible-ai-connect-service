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

from abc import abstractmethod
from datetime import datetime
from unittest.mock import Mock, patch

from django.test import override_settings
from oauth2client.service_account import ServiceAccountCredentials
from slack_sdk.errors import SlackApiError

from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC
from ansible_ai_connect.users.reports.exceptions import ReportGenerationException
from ansible_ai_connect.users.reports.postman import (
    BasePostman,
    GoogleDrivePostman,
    Report,
    Reports,
    SlackWebApiPostman,
    SlackWebhookPostman,
    StdoutPostman,
)


class BasePostmanTest(WisdomServiceAPITestCaseBaseOIDC):

    def test_make_message_body(self):
        reports: Reports = Reports(data=[Report("title1", "data1"), Report("title2", "data2")])
        body: dict = BasePostman.make_message_body(reports)
        self.assertEqual(len(body), 5)
        self.assertEqual(body[0]["type"], "section")
        self.assertEqual(body[0]["text"]["text"], "*Reports*")
        self.assertEqual(body[1]["type"], "section")
        self.assertEqual(body[1]["text"]["text"], "*title1*")
        self.assertEqual(body[2]["type"], "section")
        self.assertEqual(body[2]["text"]["text"], "```data1```")
        self.assertEqual(body[3]["type"], "section")
        self.assertEqual(body[3]["text"]["text"], "*title2*")
        self.assertEqual(body[4]["type"], "section")
        self.assertEqual(body[4]["text"]["text"], "```data2```")

    def test_make_report_title(self):
        title = BasePostman.make_report_title("title")
        self.assertEqual(title, "title")

    def test_make_report_title_with_plan_id(self):
        title = BasePostman.make_report_title("title", 1)
        self.assertEqual(title, "title for plan id: 1")

    def test_make_report_title_with_created_after(self):
        title = BasePostman.make_report_title(
            "title", created_after=datetime.fromisoformat("2024-12-25")
        )
        self.assertEqual(title, "title (since 2024-12-25 00:00:00)")

    def test_make_report_title_with_created_before(self):
        title = BasePostman.make_report_title(
            "title", created_before=datetime.fromisoformat("2024-12-25")
        )
        self.assertEqual(title, "title (before 2024-12-25 00:00:00)")

    def test_make_report_title_with_created_after_and_created_before(self):
        title = BasePostman.make_report_title(
            "title",
            created_after=datetime.fromisoformat("2024-01-01"),
            created_before=datetime.fromisoformat("2024-12-25"),
        )
        self.assertEqual(title, "title (2024-01-01 00:00:00 to 2024-12-25 00:00:00)")

    def test_make_report_title_with_created_after_and_created_before_and_plan(self):
        title = BasePostman.make_report_title(
            "title", 1, datetime.fromisoformat("2024-01-01"), datetime.fromisoformat("2024-12-25")
        )
        self.assertEqual(title, "title (2024-01-01 00:00:00 to 2024-12-25 00:00:00) for plan id: 1")


class StdoutPostmanTest(WisdomServiceAPITestCaseBaseOIDC):

    def test_logging(self):
        reports: Reports = Reports(data=[Report("title", "data")])

        with self.assertLogs(logger="root", level="INFO") as log:
            StdoutPostman().send_reports(reports)
            self.assertInLog("*Reports*", log)
            self.assertInLog("*title*", log)
            self.assertInLog("```data```", log)


class BaseSlackPostmanTest(WisdomServiceAPITestCaseBaseOIDC):

    @abstractmethod
    def get_postman(self) -> BasePostman:
        pass

    def assert_send_reports(self, handler_method):
        reports: Reports = Reports(data=[Report("title", "data")])
        response = Mock()
        response.status_code = 200
        handler_method.return_value = response

        postman = self.get_postman()
        postman.send_reports(reports)

        args = handler_method.call_args_list
        body: dict = args[0].kwargs["blocks"]
        self.assertEqual(len(body), 3)
        self.assertEqual(body[0]["type"], "section")
        self.assertEqual(body[0]["text"]["text"], "*Reports*")
        self.assertEqual(body[1]["type"], "section")
        self.assertEqual(body[1]["text"]["text"], "*title*")
        self.assertEqual(body[2]["type"], "section")
        self.assertEqual(body[2]["text"]["text"], "```data```")

    def assert_send_reports_with_http_exception(self, handler_method):
        reports: Reports = Reports(data=[Report("title", "data")])
        response = Mock()
        response.status_code = 500
        handler_method.return_value = response

        postman = self.get_postman()
        with self.assertRaises(ReportGenerationException):
            with self.assertLogs(logger="root", level="INFO") as log:
                postman.send_reports(reports)
                self.assertInLog("Failed to post reports", log)

    def assert_send_reports_with_slack_exception(self, handler_method):
        reports: Reports = Reports(data=[Report("title", "data")])
        handler_method.side_effect = SlackApiError("slack-error", Mock())

        postman = self.get_postman()
        with self.assertRaises(ReportGenerationException):
            with self.assertLogs(logger="root", level="INFO") as log:
                postman.send_reports(reports)
                self.assertInLog("An error occurred posting report", log)


@override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={"slack-webhook-url": "webhook-url"})
class SlackWebhookPostmanTest(BaseSlackPostmanTest):

    def get_postman(self) -> BasePostman:
        return SlackWebhookPostman()

    @patch("ansible_ai_connect.users.reports.postman.WebhookClient")
    def test_send_reports(self, handler):
        self.assert_send_reports(handler.return_value.send)
        handler.assert_called_once_with("webhook-url")

    @patch("ansible_ai_connect.users.reports.postman.WebhookClient")
    def test_send_reports_with_http_exception(self, handler):
        self.assert_send_reports_with_http_exception(handler.return_value.send)

    @patch("ansible_ai_connect.users.reports.postman.WebhookClient")
    def test_send_reports_with_slack_exception(self, handler):
        self.assert_send_reports_with_slack_exception(handler.return_value.send)


@override_settings(
    ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
        "slack-token": "slack-token",
        "slack-channel-id": "slack-channel-id",
    }
)
class SlackWebApiPostmanTest(BaseSlackPostmanTest):

    def get_postman(self) -> BasePostman:
        return SlackWebApiPostman()

    @patch("ansible_ai_connect.users.reports.postman.WebClient")
    def test_send_reports(self, handler):
        self.assert_send_reports(handler.return_value.chat_postMessage)
        handler.assert_called_once_with(token="slack-token")

    @patch("ansible_ai_connect.users.reports.postman.WebClient")
    def test_send_reports_with_http_exception(self, handler):
        self.assert_send_reports_with_http_exception(handler.return_value.chat_postMessage)

    @patch("ansible_ai_connect.users.reports.postman.WebClient")
    def test_send_reports_with_slack_exception(self, handler):
        self.assert_send_reports_with_slack_exception(handler.return_value.chat_postMessage)


@override_settings(
    ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
        "gdrive-folder-name": "test-folder",
        "gdrive-project-id": "test-project-id",
        "gdrive-private-key-id": "test-private-key-id",
        "gdrive-private-key": "test-private-key",
        "gdrive-client-email": "test-client-email",
        "gdrive-client-id": "test-client-id",
    }
)
class GoogleDrivePostmanTest(WisdomServiceAPITestCaseBaseOIDC):

    def assert_send_reports(
        self,
        sa_credentials: Mock,
        g_drive: Mock,
        g_auth: Mock,
        reports: Reports,
        created_before: datetime,
    ):
        g_drive.return_value.ListFile.return_value.GetList.return_value = [
            {"id": "test-folder-id", "title": "test-folder"}
        ]

        postman = GoogleDrivePostman()
        postman.send_reports(reports)

        self.assertEqual(g_auth.return_value.credentials, sa_credentials.return_value)
        g_drive.assert_called_once_with(g_auth.return_value)

        file_name_prefix = created_before.strftime("%Y%m%d")
        create_file = g_drive.return_value.CreateFile
        create_file.assert_called_once_with(
            {"parents": [{"id": "test-folder-id"}], "title": f"{file_name_prefix}_title.csv"}
        )
        create_file.return_value.SetContentString.assert_called_once_with("data")
        create_file.return_value.Upload.assert_called_once()

    @patch("ansible_ai_connect.users.reports.postman.GoogleAuth")
    @patch("ansible_ai_connect.users.reports.postman.GoogleDrive")
    @patch.object(
        ServiceAccountCredentials, "from_json_keyfile_dict", return_value={"credentials": "secret"}
    )
    def test_send_reports(self, sa_credentials, g_drive, g_auth):
        reports: Reports = Reports(data=[Report("title", "data")])
        self.assert_send_reports(sa_credentials, g_drive, g_auth, reports, datetime.now())

    @patch("ansible_ai_connect.users.reports.postman.GoogleAuth")
    @patch("ansible_ai_connect.users.reports.postman.GoogleDrive")
    @patch.object(
        ServiceAccountCredentials, "from_json_keyfile_dict", return_value={"credentials": "secret"}
    )
    def test_send_reports_with_created_before(self, sa_credentials, g_drive, g_auth):
        created_before = datetime.fromisoformat("20241231")
        reports: Reports = Reports(data=[Report("title", "data")], created_before=created_before)
        self.assert_send_reports(sa_credentials, g_drive, g_auth, reports, created_before)

    @patch("ansible_ai_connect.users.reports.postman.GoogleAuth")
    @patch("ansible_ai_connect.users.reports.postman.GoogleDrive")
    @patch.object(
        ServiceAccountCredentials, "from_json_keyfile_dict", return_value={"credentials": "secret"}
    )
    def test_send_reports_with_missing_folder(self, *args, **kwargs):
        reports: Reports = Reports(data=[Report("title", "data")])

        postman = GoogleDrivePostman()
        with self.assertRaises(ReportGenerationException):
            with self.assertLogs(logger="root", level="INFO") as log:
                postman.send_reports(reports)
                self.assertInLog("Unable to locate folder", log)

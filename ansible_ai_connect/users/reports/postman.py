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
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from urllib import parse

from django.conf import settings
from django.utils import timezone
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.webhook import WebhookClient

from ansible_ai_connect.users.reports.exceptions import (
    ReportConfigurationException,
    ReportGenerationException,
)

logger = logging.getLogger(__name__)


class Report:
    def __init__(self, title: str, data: str) -> None:
        super().__init__()
        self.title = title
        self.data = data


class Reports:
    def __init__(
        self,
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        data: List[Report] = (),
    ) -> None:
        super().__init__()
        self.plan_id = plan_id
        self.created_after = created_after
        self.created_before = created_before
        self.data = data


class BasePostman(ABC):

    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def make_message_body(reports: Reports):
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Reports*"}},
        ]
        for report in reports.data:
            title = BasePostman.make_report_title(
                report.title, reports.plan_id, reports.created_after, reports.created_before
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*"}})
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"```{report.data}```"}}
            )
        return blocks

    @staticmethod
    def make_report_title(
        title,
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        date_range = ""
        plan_detail = f" for plan id: {plan_id}" if plan_id else ""
        if created_after and not created_before:
            date_range = f" (since {created_after.strftime(BasePostman.DATE_FORMAT)})"
        if not created_after and created_before:
            date_range = f" (before {created_before.strftime(BasePostman.DATE_FORMAT)})"
        if created_after and created_before:
            date_range = (
                f" ({created_after.strftime(BasePostman.DATE_FORMAT)} to "
                f"{created_before.strftime(BasePostman.DATE_FORMAT)})"
            )

        return f"{title}{date_range}{plan_detail}"

    @abstractmethod
    def send_reports(self, reports: Reports):
        pass


class NoopPostman(BasePostman):

    def send_reports(self, reports: Reports):
        # NOOP
        pass


class StdoutPostman(BasePostman):

    def send_reports(self, reports: Reports):
        logger.info(json.dumps(BasePostman.make_message_body(reports), indent=2))


class SlackWebhookPostman(BasePostman):

    def __init__(self):
        super().__init__()
        config = settings.ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG
        if not config.get("slack-webhook-url"):
            raise ReportConfigurationException("'slack-webhook-url' is not set.")
        self.webhook_url = config.get("slack-webhook-url")

    def send_reports(self, reports: Reports):
        try:
            webhook = WebhookClient(self.webhook_url)
            response = webhook.send(text="fallback", blocks=BasePostman.make_message_body(reports))
            if response.status_code != 200:
                logger.error(f"Failed to post reports. See response for details: {response.body}")
                raise ReportGenerationException("Failed to post reports.")

        except SlackApiError as e:
            logger.error(f"An error occurred posting reports: {e}")
            raise ReportGenerationException(e)


class SlackWebApiPostman(BasePostman):

    def __init__(self):
        super().__init__()
        config = settings.ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG
        if not config.get("slack-token"):
            raise ReportConfigurationException("'slack-token' is not set.")
        if not config.get("slack-channel-id"):
            raise ReportConfigurationException("'slack-channel-id' is not set.")
        self.slack_token = config.get("slack-token")
        self.slack_channel_id = config.get("slack-channel-id")

    def send_reports(self, reports: Reports):
        try:
            client = WebClient(token=self.slack_token)
            response = client.chat_postMessage(
                channel=self.slack_channel_id, blocks=BasePostman.make_message_body(reports)
            )
            if response.status_code != 200:
                logger.error(f"Failed to post reports. See response for details {response}.")
                raise ReportGenerationException("Failed to post reports.")

        except SlackApiError as e:
            logger.error(f"An error occurred posting reports: {e}")
            raise ReportGenerationException(e)


class GoogleDrivePostman(BasePostman):

    def __init__(self):
        super().__init__()
        config = settings.ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG
        if not config.get("gdrive-folder-name"):
            raise ReportConfigurationException("'gdrive-folder-name' is not set.")
        if not config.get("gdrive-project-id"):
            raise ReportConfigurationException("'gdrive-project-id' is not set.")
        if not config.get("gdrive-private-key-id"):
            raise ReportConfigurationException("'gdrive-private-key-id' is not set.")
        if not config.get("gdrive-private-key"):
            raise ReportConfigurationException("'gdrive-private-key' is not set.")
        if not config.get("gdrive-client-email"):
            raise ReportConfigurationException("'gdrive-client-email' is not set.")
        if not config.get("gdrive-client-id"):
            raise ReportConfigurationException("'gdrive-client-id' is not set.")
        self.folder_name = config.get("gdrive-folder-name")
        self.project_id = config.get("gdrive-project-id")
        self.private_key_id = config.get("gdrive-private-key-id")
        self.private_key = config.get("gdrive-private-key")
        self.client_email = config.get("gdrive-client-email")
        self.client_id = config.get("gdrive-client-id")

    def get_drive(self) -> GoogleDrive:
        gauth = GoogleAuth()

        credentials = {
            "type": "service_account",
            "project_id": self.project_id,
            "private_key_id": self.private_key_id,
            "private_key": self.private_key,
            "client_email": self.client_email,
            "client_id": self.client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": (
                "https://www.googleapis.com/robot/v1/metadata/x509/",
                parse.quote_plus(self.client_email),
            ),
            "universe_domain": "googleapis.com",
        }

        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            credentials, scopes=["https://www.googleapis.com/auth/drive"]
        )

        return GoogleDrive(gauth)

    @staticmethod
    def create_filename(title: str, report_date: datetime):
        if report_date.tzinfo is None:
            raise ValueError
        return f"{report_date.strftime('%Y%m%d')}_{title}.csv"

    def send_reports(self, reports: Reports):
        drive = self.get_drive()
        folder_id = self.get_folder_id(drive)
        report_date = reports.created_before or timezone.now()

        for report in reports.data:
            file_name = self.create_filename(report.title, report_date)
            file = drive.CreateFile({"parents": [{"id": folder_id}], "title": file_name})
            file.SetContentString(report.data)
            file.Upload()

    def get_folder_id(self, drive: GoogleDrive) -> str:
        folder_id = None
        folder_list = drive.ListFile({"q": "trashed=false"}).GetList()

        for folder in folder_list:
            if folder["title"] == self.folder_name:
                folder_id = folder["id"]

        if folder_id is None:
            logger.error(f"Unable to locate folder '{self.folder_name}' on Google Drive.")
            raise ReportGenerationException(
                f"Unable to locate folder '{self.folder_name}' on Google Drive."
            )

        return folder_id

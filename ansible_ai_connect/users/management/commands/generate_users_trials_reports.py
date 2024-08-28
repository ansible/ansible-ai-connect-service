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
from argparse import ArgumentTypeError
from datetime import datetime
from typing import Optional, cast

from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ansible_ai_connect.users.constants import TRIAL_PLAN_NAME
from ansible_ai_connect.users.models import Plan
from ansible_ai_connect.users.reports.generators import (
    UserMarketingReportGenerator,
    UserTrialsReportGenerator,
)
from ansible_ai_connect.users.reports.postman import Report, Reports, StdoutPostman


class Command(BaseCommand):

    @staticmethod
    def generate_user_trials_report(
        plan_id: int,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> str:
        generator = UserTrialsReportGenerator()
        return generator.generate(plan_id, created_after, created_before)

    @staticmethod
    def generate_user_marketing_report(
        plan_id: int,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> str:
        generator = UserMarketingReportGenerator()
        return generator.generate(plan_id, created_after, created_before)

    @staticmethod
    def iso_datetime_type(arg_datetime: str):
        try:
            return datetime.fromisoformat(arg_datetime)
        except ValueError:
            msg = f"Given datetime '{arg_datetime}' is invalid. Expected ISO-8601 format."
            raise ArgumentTypeError(msg)

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do nothing", default=False)
        parser.add_argument("--plan-id", help="Trail plan_id", type=int)
        parser.add_argument(
            "--created-after",
            help="ISO-8601 formatted datetime after which trials were accepted.",
            type=Command.iso_datetime_type,
        )
        parser.add_argument(
            "--created-before",
            help="ISO-8601 formatted datetime before which trials were accepted.",
            type=Command.iso_datetime_type,
        )
        parser.add_argument(
            "--auto-range",
            action="store_true",
            help=(
                "Uses date range based on execution time: "
                "created-before=now(). created-after=now() minus one day."
                "Time defaults to midnight."
            ),
            default=False,
        )

    def handle(self, dry_run, plan_id, created_after, created_before, auto_range, *args, **options):
        created_after = created_after if created_after else None
        created_before = created_before if created_before else None
        plan = Plan.objects.get(id=plan_id) if plan_id else Plan.objects.get(name=TRIAL_PLAN_NAME)

        if auto_range:
            created_before = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            created_after = created_before - relativedelta(days=1)

        if dry_run:
            self.stdout.write("Reports not sent due to --dry-run parameter.")

        # Generate and send reports
        user_trials_report = Command.generate_user_trials_report(
            plan.id, created_after, created_before
        )
        user_marketing_report = Command.generate_user_marketing_report(
            plan.id, created_after, created_before
        )

        # Lookup postman
        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        postman = StdoutPostman() if dry_run else ai_config.get_reports_postman()

        # Send reports
        try:
            postman.send_reports(
                Reports(
                    plan.id,
                    created_after,
                    created_before,
                    [
                        Report("User marketing preferences", user_marketing_report),
                        Report("User trials acceptance", user_trials_report),
                    ],
                )
            )
        except Exception as e:
            self.stderr.write(str(e))
            raise CommandError("Failed to post reports.")

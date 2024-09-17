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
import re
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from django.test import override_settings

from ansible_ai_connect.test_utils import (
    WisdomServiceAPITestCaseBaseOIDC,
    create_user_with_provider,
)
from ansible_ai_connect.users.constants import USER_SOCIAL_AUTH_PROVIDER_OIDC
from ansible_ai_connect.users.models import Plan
from ansible_ai_connect.users.reports.generators import (
    BaseGenerator,
    UserMarketingReportGenerator,
    UserTrialsReportGenerator,
)


class BaseReportGeneratorTest:

    def initialise(self, test: WisdomServiceAPITestCaseBaseOIDC):
        self.test = test

        # A User that has a trial plan
        # DummyCheck/AUTHZ_BACKEND_TYPE=dummy sets the User's name to "Robert Surcouf"
        self.trial_user = create_user_with_provider(
            given_name="Robert",
            family_name="Surcouf",
            username="trial_user",
            email="trial_user@somewhere.com",
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_org_id=1981,
        )
        self.trial_user2 = create_user_with_provider(
            given_name="Anne",
            family_name="Bonny",
            username="another_trial_user",
            email="anne.bonny@somewhere.com",
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_org_id=1720,
        )
        self.trial_plan, _ = Plan.objects.get_or_create(
            name="Trial of 10 days", expires_after="10 days"
        )
        self.trial_plan.created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

    def cleanup(self):
        self.trial_user.delete()
        self.trial_user2.delete()
        self.trial_plan.delete()

    def get_report_header(self) -> str:
        pass

    def get_report_generator(self) -> BaseGenerator:
        pass

    def add_plan_to_user(self):
        self.trial_user.plans.add(self.trial_plan)
        self.trial_user2.plans.add(self.trial_plan)

    def test_get_report_headers(self):
        r = self.get_report_generator().generate()
        self.test.assertIn(self.get_report_header(), r)

    def test_get_report_with_no_plans(self):
        r = self.get_report_generator().generate()
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertNotIn("Robert,Surcouf", r)
        self.test.assertNotIn("Trial of 10 days", r)

    def test_get_report_with_plans(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate()
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertIn("Robert,Surcouf", r)
        self.test.assertIn("Trial of 10 days", r)

    def test_get_report_filter_by_existing_plan_id(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(plan_id=self.trial_plan.id)
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertIn("Robert,Surcouf", r)
        self.test.assertIn(str(self.trial_user.uuid), r)
        self.test.assertIn("Trial of 10 days", r)

    def test_get_report_filter_by_non_existing_plan_id(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(plan_id=999)
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertNotIn("Robert,Surcouf", r)
        self.test.assertNotIn("Trial of 10 days", r)

    def test_get_report_filter_by_created_after(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(
            created_after=self.trial_plan.created_at + relativedelta(days=-1)
        )
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertIn("Robert,Surcouf", r)
        self.test.assertIn("Trial of 10 days", r)

    def test_get_report_filter_by_created_after_trail_date(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(
            created_after=self.trial_user.userplan_set.first().created_at + relativedelta(days=1)
        )
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertNotIn("Robert,Surcouf", r)
        self.test.assertNotIn("Trial of 10 days", r)

    def test_get_report_filter_by_created_before(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(
            created_before=self.trial_user.userplan_set.first().created_at + relativedelta(days=1)
        )
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertIn("Robert,Surcouf", r)
        self.test.assertIn("Trial of 10 days", r)

    def test_get_report_filter_by_created_before_trial_date(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(
            created_before=self.trial_plan.created_at + relativedelta(days=-1)
        )
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertNotIn("Robert,Surcouf", r)
        self.test.assertNotIn("Trial of 10 days", r)


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestUserTrialsReportGenerator(WisdomServiceAPITestCaseBaseOIDC, BaseReportGeneratorTest):

    def setUp(self):
        super().setUp()
        super().initialise(self)

    def tearDown(self):
        super().tearDown()
        super().cleanup()

    def get_report_header(self) -> str:
        return (
            "OrgId,UUID,First name,Last name,Organization name,"
            "Plan name,Trial started,Trial expired_at,Org has_api_key"
        )

    def get_report_generator(self) -> BaseGenerator:
        return UserTrialsReportGenerator()

    def test_get_report_in_the_right_order(self):
        self.add_plan_to_user()

        def build_user(name, org_id):
            u = create_user_with_provider(
                given_name=name,
                family_name="user",
                username=f"{name}_user",
                email=f"{name}@somewhere.com",
                provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
                rh_org_id=org_id,
            )
            u.plans.add(self.trial_plan)
            return u

        users = [
            build_user(*i)
            for i in [
                ("3rd--", 1980),
                ("5th--", 1990),
                ("1st--", 1970),
                ("2nd--", 1975),
                ("4th--", 1985),
            ]
        ]
        r = self.get_report_generator().generate()

        # Ensure we've got the lines properly ordered
        self.test.assertTrue(
            re.search("1st--.*2nd--.*3rd--.*4th--.*5th--", r, re.MULTILINE | re.DOTALL)
        )
        for u in users:
            u.delete()


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestUserMarketingReportGenerator(WisdomServiceAPITestCaseBaseOIDC, BaseReportGeneratorTest):

    def setUp(self):
        super().setUp()
        super().initialise(self)

    def tearDown(self):
        super().tearDown()
        super().cleanup()

    def get_report_header(self) -> str:
        return "OrgId,UUID,First name,Last name,Organization name,Email," "Plan name,Trial started"

    def get_report_generator(self) -> BaseGenerator:
        return UserMarketingReportGenerator()

    def add_plan_to_user(self):
        super().add_plan_to_user()
        up = self.trial_user.userplan_set.first()
        up.accept_marketing = True
        up.save()

    def test_non_marketing_user_no_in_answer(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate()
        self.test.assertNotIn("Anne", r)

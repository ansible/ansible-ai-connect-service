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
            username="trial_user",
            email="trial_user@somewhere.com",
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_org_id=1981,
        )
        self.trial_plan, _ = Plan.objects.get_or_create(
            name="Trial of 10 days", expires_after="10 days"
        )

    def cleanup(self):
        self.trial_user.delete()
        self.trial_plan.delete()

    def get_report_header(self) -> str:
        pass

    def get_report_generator(self) -> BaseGenerator:
        pass

    def add_plan_to_user(self):
        self.trial_user.plans.add(self.trial_plan)

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
            created_after=self.trial_plan.created_at + relativedelta(days=1)
        )
        self.test.assertIn(self.get_report_header(), r)
        self.test.assertNotIn("Robert,Surcouf", r)
        self.test.assertNotIn("Trial of 10 days", r)

    def test_get_report_filter_by_created_before(self):
        self.add_plan_to_user()
        r = self.get_report_generator().generate(
            created_before=self.trial_plan.created_at + relativedelta(days=1)
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
        return "First name,Last name,Organization name,Plan name,Trial started"

    def get_report_generator(self) -> BaseGenerator:
        return UserTrialsReportGenerator()


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestUserMarketingReportGenerator(WisdomServiceAPITestCaseBaseOIDC, BaseReportGeneratorTest):

    def setUp(self):
        super().setUp()
        super().initialise(self)

    def tearDown(self):
        super().tearDown()
        super().cleanup()

    def get_report_header(self) -> str:
        return "First name,Last name,Email,Plan name,Trial started"

    def get_report_generator(self) -> BaseGenerator:
        return UserMarketingReportGenerator()

    def add_plan_to_user(self):
        super().add_plan_to_user()
        up = self.trial_user.userplan_set.first()
        up.accept_marketing = True
        up.save()

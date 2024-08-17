from textwrap import dedent

from django.conf import settings
from django.utils import timezone


class OneClickTrial:

    def __init__(self, user):
        self.user = user

    def is_available(self):
        return (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and self.user.is_authenticated
            and self.user.is_oidc_user
            and self.user.rh_org_has_subscription
            and not self.user.organization.has_api_key
        )

    def get_plans(self):
        active_plan = None
        expired_plan = None
        days_left: int = 0

        if hasattr(self.user, "userplan_set"):
            for up in self.user.userplan_set.all():
                if up.is_active:
                    days_left = (up.expired_at - timezone.now()).days
                    active_plan = up
                else:
                    expired_plan = up

        return active_plan, expired_plan, days_left

    def get_markdown(self, host):
        markdown_value = ""

        if self.is_available():
            active_plan, expired_plan, _ = self.get_plans()

            if active_plan:
                expired_at = active_plan.expired_at.strftime("%Y-%m-%d")
                markdown_value = f"""
                    Logged in as: {self.user.username}<br>
                    Plan: {active_plan.plan.name}<br>
                    Expiration: {expired_at}
                """
            elif expired_plan:
                markdown_value = f"""
                    Logged in as: {self.user.username}<br>
                    Your trial period has expired.
                """
            else:
                markdown_value = f"""
                    Logged in as: {self.user.username}<br><br>
                    Your account is not configured to use Ansible Lightspeed.
                    Start a trial to Ansible Lightspeed with IBM watsonx Code Assistant
                    by following the link below.<br><br>
                    <a href = "https://{host}/trial/">Start trial</a>
                """

        return dedent(markdown_value).strip()

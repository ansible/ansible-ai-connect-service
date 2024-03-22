from django.test import TestCase

from ansible_wisdom.organizations.models import Organization


class TestOrganization(TestCase):
    def test_org_with_telemetry_schema_2_opted_in(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)

    def test_org_with_telemetry_schema_2_opted_out(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)

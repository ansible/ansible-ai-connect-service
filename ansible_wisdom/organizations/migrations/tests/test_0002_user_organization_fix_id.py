from django_test_migrations.contrib.unittest_case import MigratorTestCase


class TestDirectMigration(MigratorTestCase):
    migrate_from = ('organizations', '0001_initial')
    migrate_to = ('organizations', '0002_user_organization_fix_id')

    def prepare(self):
        user = self.old_state.apps.get_model('users', 'User')
        user.objects.create(organization_id=123)

    def test_migration_0002_user_organization_fix_id(self):
        user_old = self.old_state.apps.get_model('users', 'User')
        self.assertFalse(hasattr(user_old, 'organization'))

        user_new = self.new_state.apps.get_model('users', 'User')
        users = user_new.objects.all()
        self.assertEqual(1, len(users))
        self.assertTrue(hasattr(users[0], 'organization'))
        self.assertIsNotNone(users[0].organization)
        self.assertEqual(123, users[0].organization.id)

        organization_new = self.new_state.apps.get_model('organizations', 'Organization')
        organizations = organization_new.objects.all()
        self.assertEqual(1, len(organizations))
        self.assertTrue(hasattr(users[0], 'organization'))
        self.assertEqual(organizations[0].id, users[0].organization.id)

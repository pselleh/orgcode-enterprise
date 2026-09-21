from uuid import uuid4

from django.contrib.auth.hashers import check_password
from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RepairedProductionMigrationTests(TransactionTestCase):
    migrate_from = ("orgcode_enterprise", "0003_enterprise_identity_models")
    migrate_to = ("orgcode_enterprise", "0006_remove_plaintext_codes")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        User = old_apps.get_model("auth", "User")
        Profile = old_apps.get_model("orgcode_enterprise", "EnterpriseLearnerProfile")
        OrgCode = old_apps.get_model("orgcode_enterprise", "OrgCode")

        users = [
            User.objects.create(
                username=f"migration-user-{index}",
                email=f"migration-user-{index}@example.org",
                password="!",
            )
            for index in range(4)
        ]
        Profile.objects.create(user_id=users[0].pk, organization_code="alpha-2027")
        for user in users[1:]:
            Profile.objects.create(user_id=user.pk, organization_code="")

        self.alpha_uuid = uuid4()
        self.beta_uuid = uuid4()
        OrgCode.objects.create(
            code="Alpha-2027",
            enterprise_customer_uuid=self.alpha_uuid,
            description="Alpha Organization",
            active=True,
            discount_percent="20.00",
            course_id="course-v1:CBA+PRIVATE101+2027",
        )
        OrgCode.objects.create(
            code="Beta-2027",
            enterprise_customer_uuid=self.beta_uuid,
            description="Beta Organization",
            active=True,
            discount_amount="10.00",
            program_id="CBA-PRIVATE-PROGRAM-2027",
        )

        self._simulate_legacy_mysql_integer_keys()

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_existing_codes_and_profiles_are_preserved_and_converted(self):
        OrgCode = self.apps.get_model("orgcode_enterprise", "OrgCode")
        Profile = self.apps.get_model("orgcode_enterprise", "EnterpriseLearnerProfile")
        Organization = self.apps.get_model("orgcode_enterprise", "Organization")
        AccessPolicy = self.apps.get_model("orgcode_enterprise", "AccessPolicy")
        Membership = self.apps.get_model("orgcode_enterprise", "OrganizationMembership")
        Grant = self.apps.get_model("orgcode_enterprise", "OrganizationAccessGrant")

        self.assertEqual(OrgCode.objects.count(), 2)
        self.assertEqual(Profile.objects.count(), 4)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(AccessPolicy.objects.count(), 2)

        alpha = OrgCode.objects.get(enterprise_customer_uuid=self.alpha_uuid)
        beta = OrgCode.objects.get(enterprise_customer_uuid=self.beta_uuid)
        self.assertTrue(check_password("ALPHA-2027", alpha.code_hash))
        self.assertTrue(check_password("BETA-2027", beta.code_hash))
        self.assertTrue(alpha.organization_id)
        self.assertTrue(alpha.access_policy_id)
        self.assertTrue(beta.organization_id)
        self.assertTrue(beta.access_policy_id)

        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Grant.objects.count(), 1)
        self.assertEqual(
            alpha.access_policy.course_permissions.count(),
            1,
        )
        self.assertEqual(
            beta.access_policy.program_permissions.count(),
            1,
        )

        with self.assertRaises(FieldDoesNotExist):
            OrgCode._meta.get_field("code")
        with self.assertRaises(FieldDoesNotExist):
            Profile._meta.get_field("organization_code")

        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND (
                            (table_name = 'orgcode_enterprise_orgcode'
                             AND column_name = 'id')
                         OR (table_name = 'orgcode_enterprise_orgcodeusage'
                             AND column_name IN ('id', 'code_id'))
                      )
                    """
                )
                migrated_types = {
                    (table_name, column_name): data_type.lower()
                    for table_name, column_name, data_type in cursor.fetchall()
                }
            self.assertEqual(set(migrated_types.values()), {"bigint"})

    def _simulate_legacy_mysql_integer_keys(self):
        if connection.vendor != "mysql":
            return

        orgcode_table = "orgcode_enterprise_orgcode"
        usage_table = "orgcode_enterprise_orgcodeusage"
        quote = connection.ops.quote_name

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT constraint_name
                FROM information_schema.key_column_usage
                WHERE constraint_schema = DATABASE()
                  AND table_name = %s
                  AND column_name = 'code_id'
                  AND referenced_table_name = %s
                  AND referenced_column_name = 'id'
                """,
                [usage_table, orgcode_table],
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            constraint_name = row[0]

            cursor.execute(
                f"ALTER TABLE {quote(usage_table)} "
                f"DROP FOREIGN KEY {quote(constraint_name)}"
            )
            cursor.execute(
                f"ALTER TABLE {quote(orgcode_table)} "
                f"MODIFY COLUMN {quote('id')} INT NOT NULL AUTO_INCREMENT"
            )
            cursor.execute(
                f"ALTER TABLE {quote(usage_table)} "
                f"MODIFY COLUMN {quote('id')} INT NOT NULL AUTO_INCREMENT, "
                f"MODIFY COLUMN {quote('code_id')} INT NOT NULL"
            )
            cursor.execute(
                f"ALTER TABLE {quote(usage_table)} "
                f"ADD CONSTRAINT {quote(constraint_name)} "
                f"FOREIGN KEY ({quote('code_id')}) "
                f"REFERENCES {quote(orgcode_table)} ({quote('id')})"
            )

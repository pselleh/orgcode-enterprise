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

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from orgcode_enterprise.models import (
    AccessPolicy,
    AccessPolicyCoursePermission,
    OrgCode,
    Organization,
    OrganizationAccessGrant,
    OrganizationMembership,
)
from orgcode_enterprise.services import (
    GENERIC_INVALID_MESSAGE,
    InvalidOrgCode,
    authorize_private_product,
    redeem_org_code,
)

class OrganizationAccessGrantTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="learner", email="learner@example.org")
        self.enterprise_uuid = uuid4()
        self.organization = Organization.objects.create(
            name="Example Agency",
            code="EXAMPLE",
            enterprise_customer_uuid=self.enterprise_uuid,
        )
        self.policy = AccessPolicy.objects.create(
            key="cba-restricted-risk-intelligence-2027",
            name="Restricted risk intelligence",
            discount_percent="20.00",
        )
        AccessPolicyCoursePermission.objects.create(
            policy=self.policy,
            course_key="course-v1:CBA+ETR211+2027",
        )
        self.org_code = OrgCode(
            organization=self.organization,
            access_policy=self.policy,
            enterprise_customer_uuid=self.enterprise_uuid,
            max_uses_per_user=1,
        )
        self.org_code.set_code(" Example-2027 ")
        self.org_code.save()

    def test_code_is_hashed_and_never_stored_as_plaintext(self):
        self.assertNotIn("EXAMPLE-2027", self.org_code.code_hash)
        self.assertTrue(self.org_code.matches_code("example-2027"))

    def test_redemption_creates_membership_and_durable_grant(self):
        grant, created = redeem_org_code(self.user, "example-2027")
        self.assertTrue(created)
        self.assertEqual(grant.access_policy, self.policy)
        self.assertEqual(str(grant.discount_percent), "20.00")
        self.assertTrue(
            OrganizationMembership.objects.filter(
                profile__user=self.user,
                organization=self.organization,
                active=True,
            ).exists()
        )

    def test_redemption_retry_is_idempotent(self):
        first, first_created = redeem_org_code(self.user, "example-2027")
        second, second_created = redeem_org_code(self.user, "example-2027")
        self.org_code.refresh_from_db()
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.org_code.times_used, 1)
        self.assertEqual(OrganizationAccessGrant.objects.filter(user=self.user).count(), 1)

    def test_private_product_authorization_checks_policy_and_product(self):
        redeem_org_code(self.user, "example-2027")
        grant = authorize_private_product(
            self.user,
            self.policy.key,
            "course",
            "course-v1:CBA+ETR211+2027",
        )
        self.assertIsNotNone(grant)
        self.assertIsNone(
            authorize_private_product(
                self.user,
                self.policy.key,
                "course",
                "course-v1:CBA+PUBLIC101+2027",
            )
        )

    def test_expired_code_returns_generic_error(self):
        self.org_code.valid_until = timezone.now() - timedelta(minutes=1)
        self.org_code.save()
        with self.assertRaisesMessage(InvalidOrgCode, GENERIC_INVALID_MESSAGE):
            redeem_org_code(self.user, "example-2027")

    def test_api_returns_public_plus_private_grant_without_echoing_code(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(reverse("orgcode_enterprise:orgcode-redeem"), {"code": "EXAMPLE-2027"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("EXAMPLE-2027", response.content.decode())

        access = client.get(reverse("orgcode_enterprise:orgcode-current-access"))
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["public_catalog_access"])
        self.assertEqual(
            access.data["organization_grants"][0]["access_policy_key"],
            "cba-restricted-risk-intelligence-2027",
        )

    def test_legacy_registration_endpoint_remains_compatible(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(reverse("orgcode_enterprise:orgcode-apply-legacy"), {"code": "EXAMPLE-2027"}, format="json")
        self.assertIn(response.status_code, {200, 201})
        self.assertEqual(response.data["message"], "Organization access applied.")

    def test_policy_assignment_requires_explicit_grant_migration(self):
        grant, _ = redeem_org_code(self.user, "example-2027")
        replacement = AccessPolicy.objects.create(key="replacement-policy", name="Replacement")
        with self.assertRaises(CommandError):
            call_command("assign_org_code_policy", self.org_code.pk, replacement.key)
        call_command(
            "assign_org_code_policy",
            self.org_code.pk,
            replacement.key,
            migrate_existing_grants=True,
            verbosity=0,
        )
        self.org_code.refresh_from_db()
        grant.refresh_from_db()
        self.assertEqual(self.org_code.access_policy, replacement)
        self.assertEqual(grant.access_policy, replacement)

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from orgcode_enterprise.models import (
    AccessPolicy,
    AccessPolicyCoursePermission,
    EnrollmentInventory,
    EnrollmentReservation,
    OrgCode,
    Organization,
    PromotionCampaign,
    PromotionOffer,
)
from orgcode_enterprise.promotion_services import (
    PromotionAccessDenied,
    PromotionCapacityExceeded,
    ReservationStateError,
    commit_enrollment,
    expire_reservations,
    quote_product_offer,
    release_enrollment,
    reserve_enrollment,
)
from orgcode_enterprise.services import redeem_org_code


class PromotionServiceTests(TestCase):
    course_key = "course-v1:CBA+PROMO101+2027"

    def setUp(self):
        user_model = get_user_model()

        self.user_one = user_model.objects.create_user(
            username="promotion-one",
            email="promotion-one@example.org",
        )
        self.user_two = user_model.objects.create_user(
            username="promotion-two",
            email="promotion-two@example.org",
        )
        self.user_three = user_model.objects.create_user(
            username="promotion-three",
            email="promotion-three@example.org",
        )

        self.now = timezone.now()

        self.campaign = PromotionCampaign.objects.create(
            key="cba-enrollment-promotion-cycle-01",
            name="CBA Enrollment Promotion Cycle 01",
            priority=10,
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=90),
        )

        self.inventory = EnrollmentInventory.objects.create(
            campaign=self.campaign,
            product_type="course",
            product_key=self.course_key,
            audience="public",
            capacity=2,
        )

        self.first_offer = PromotionOffer.objects.create(
            inventory=self.inventory,
            name="First learner tier",
            priority=10,
            tier_limit=1,
            discount_percent="25.00",
            currency="USD",
        )

        self.standard_offer = PromotionOffer.objects.create(
            inventory=self.inventory,
            name="Continuing promotion tier",
            priority=20,
            discount_percent="10.00",
            currency="USD",
        )

    def reserve(self, user, **kwargs):
        values = {
            "user": user,
            "product_type": "course",
            "product_key": self.course_key,
            "source": "course_filter",
            "now": self.now,
        }
        values.update(kwargs)
        return reserve_enrollment(**values)

    def create_organization_inventory(self):
        restricted_key = "course-v1:CBA+PRIVATE101+2027"
        enterprise_uuid = uuid4()

        organization = Organization.objects.create(
            name="Example Partner",
            code="PARTNER",
            enterprise_customer_uuid=enterprise_uuid,
        )

        policy = AccessPolicy.objects.create(
            key="cba-private-partner-catalog",
            name="CBA Private Partner Catalog",
        )

        AccessPolicyCoursePermission.objects.create(
            policy=policy,
            course_key=restricted_key,
        )

        org_code = OrgCode(
            organization=organization,
            access_policy=policy,
            enterprise_customer_uuid=enterprise_uuid,
            usage_limit=100,
            max_uses_per_user=1,
        )
        org_code.set_code("PARTNER-ACCESS-2027")
        org_code.save()

        inventory = EnrollmentInventory.objects.create(
            campaign=self.campaign,
            product_type="course",
            product_key=restricted_key,
            audience="organization",
            organization=organization,
            access_policy=policy,
            capacity=5,
        )

        PromotionOffer.objects.create(
            inventory=inventory,
            name="Partner discount",
            priority=10,
            discount_percent="20.00",
            currency="USD",
        )

        return restricted_key, org_code, inventory

    def test_quote_does_not_reserve_a_seat(self):
        quote = quote_product_offer(
            self.user_one,
            "course",
            self.course_key,
            now=self.now,
        )

        self.assertEqual(
            quote["campaign_key"],
            self.campaign.key,
        )
        self.assertEqual(
            quote["discount_percent"],
            Decimal("25.00"),
        )
        self.assertEqual(quote["capacity_remaining"], 2)
        self.assertEqual(
            EnrollmentReservation.objects.count(),
            0,
        )

    def test_reservation_retry_is_idempotent(self):
        first, first_created = self.reserve(self.user_one)
        second, second_created = self.reserve(self.user_one)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            EnrollmentReservation.objects.count(),
            1,
        )

    def test_later_learner_receives_next_discount_tier(self):
        first, _ = self.reserve(self.user_one)

        commit_enrollment(
            first.pk,
            enrollment_reference=self.course_key,
            user=self.user_one,
            now=self.now + timedelta(seconds=1),
        )

        second, created = self.reserve(
            self.user_two,
            now=self.now + timedelta(seconds=2),
        )

        self.assertTrue(created)
        self.assertEqual(second.offer, self.standard_offer)
        self.assertEqual(
            second.discount_percent,
            Decimal("10.00"),
        )

    def test_inventory_capacity_is_enforced(self):
        self.reserve(self.user_one)
        self.reserve(self.user_two)

        with self.assertRaises(PromotionCapacityExceeded):
            self.reserve(self.user_three)

    def test_expired_reservation_releases_seat_and_tier(self):
        first, _ = self.reserve(
            self.user_one,
            reservation_ttl=timedelta(minutes=1),
        )

        expired = expire_reservations(
            now=self.now + timedelta(minutes=2),
        )

        self.assertEqual(expired, 1)

        first.refresh_from_db()
        self.assertEqual(first.state, "expired")

        second, created = self.reserve(
            self.user_two,
            now=self.now + timedelta(minutes=2),
        )

        self.assertTrue(created)
        self.assertEqual(second.offer, self.first_offer)

    def test_commit_is_idempotent(self):
        reservation, _ = self.reserve(self.user_one)

        first, first_changed = commit_enrollment(
            reservation.pk,
            enrollment_reference=self.course_key,
            user=self.user_one,
            now=self.now + timedelta(seconds=1),
        )

        second, second_changed = commit_enrollment(
            reservation.pk,
            enrollment_reference="ignored-retry",
            user=self.user_one,
            now=self.now + timedelta(seconds=2),
        )

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(first.pk, second.pk)

        second.refresh_from_db()
        self.assertEqual(second.state, "committed")
        self.assertEqual(
            second.enrollment_reference,
            self.course_key,
        )

    def test_expired_reservation_cannot_be_committed(self):
        reservation, _ = self.reserve(
            self.user_one,
            reservation_ttl=timedelta(minutes=1),
        )

        with self.assertRaises(ReservationStateError):
            commit_enrollment(
                reservation.pk,
                user=self.user_one,
                now=self.now + timedelta(minutes=2),
            )

        reservation.refresh_from_db()
        self.assertEqual(reservation.state, "expired")

    def test_unenrollment_releases_capacity_when_enabled(self):
        self.inventory.capacity = 1
        self.inventory.save()

        first, _ = self.reserve(self.user_one)

        commit_enrollment(
            first.pk,
            user=self.user_one,
            now=self.now + timedelta(seconds=1),
        )

        released, changed = release_enrollment(
            first.pk,
            user=self.user_one,
            now=self.now + timedelta(seconds=2),
        )

        self.assertTrue(changed)
        self.assertEqual(released.state, "released")

        second, created = self.reserve(
            self.user_two,
            now=self.now + timedelta(seconds=3),
        )

        self.assertTrue(created)
        self.assertEqual(second.offer, self.first_offer)

    def test_committed_seat_remains_when_release_is_disabled(self):
        self.inventory.capacity = 1
        self.inventory.release_on_unenrollment = False
        self.inventory.save()

        first, _ = self.reserve(self.user_one)

        commit_enrollment(
            first.pk,
            user=self.user_one,
            now=self.now + timedelta(seconds=1),
        )

        retained, changed = release_enrollment(
            first.pk,
            user=self.user_one,
            now=self.now + timedelta(seconds=2),
        )

        self.assertFalse(changed)
        self.assertEqual(retained.state, "committed")

        with self.assertRaises(PromotionCapacityExceeded):
            self.reserve(
                self.user_two,
                now=self.now + timedelta(seconds=3),
            )

    def test_organization_inventory_requires_active_grant(self):
        restricted_key, org_code, inventory = (
            self.create_organization_inventory()
        )

        with self.assertRaises(PromotionAccessDenied):
            reserve_enrollment(
                self.user_two,
                "course",
                restricted_key,
                source="course_filter",
            )

        grant, created = redeem_org_code(
            self.user_one,
            "PARTNER-ACCESS-2027",
        )

        self.assertTrue(created)

        reservation, reserved = reserve_enrollment(
            self.user_one,
            "course",
            restricted_key,
            source="course_filter",
        )

        self.assertTrue(reserved)
        self.assertEqual(reservation.inventory, inventory)
        self.assertEqual(
            reservation.organization_access_grant,
            grant,
        )

        self.assertIsNotNone(org_code.pk)

    def test_code_redemption_does_not_consume_enrollment_seat(self):
        restricted_key, _org_code, _inventory = (
            self.create_organization_inventory()
        )

        redeem_org_code(
            self.user_one,
            "PARTNER-ACCESS-2027",
        )

        self.assertEqual(
            EnrollmentReservation.objects.filter(
                inventory__product_key=restricted_key,
            ).count(),
            0,
        )

    def test_unmanaged_product_does_not_create_reservation(self):
        reservation, created = reserve_enrollment(
            self.user_one,
            "course",
            "course-v1:CBA+UNMANAGED101+2027",
            source="course_filter",
        )

        self.assertIsNone(reservation)
        self.assertFalse(created)

    def test_certificate_program_inventory_is_supported(self):
        program_code = "CBA-CERTIFICATE-2027"

        inventory = EnrollmentInventory.objects.create(
            campaign=self.campaign,
            product_type="program",
            product_key=program_code,
            audience="public",
            capacity=10,
        )

        offer = PromotionOffer.objects.create(
            inventory=inventory,
            name="Certificate promotion",
            priority=10,
            discount_amount="50.00",
            currency="USD",
        )

        reservation, created = reserve_enrollment(
            self.user_one,
            "program",
            program_code,
            source="program_api",
            now=self.now,
        )

        self.assertTrue(created)
        self.assertEqual(reservation.offer, offer)
        self.assertEqual(
            reservation.discount_amount,
            Decimal("50.00"),
        )

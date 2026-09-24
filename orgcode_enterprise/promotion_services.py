"""Atomic promotion, discount-tier, and enrollment-seat services."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from orgcode_enterprise.models import (
    EnrollmentInventory,
    EnrollmentReservation,
    OrganizationAccessGrant,
    PromotionOffer,
)


DEFAULT_RESERVATION_TTL = timedelta(minutes=15)
VALID_PRODUCT_TYPES = {"course", "program"}


class PromotionError(ValueError):
    """Base exception for promotion and enrollment-inventory failures."""


class PromotionAccessDenied(PromotionError):
    """The learner is not eligible for the selected inventory."""


class PromotionCapacityExceeded(PromotionError):
    """No enrollment or discount-tier capacity remains."""


class PromotionUnavailable(PromotionError):
    """Promotion configuration exists but is not presently available."""


class ReservationStateError(PromotionError):
    """A reservation cannot make the requested state transition."""


def _validate_product(product_type, product_key):
    if product_type not in VALID_PRODUCT_TYPES:
        raise PromotionError("product_type must be course or program.")

    if not str(product_key or "").strip():
        raise PromotionError("product_key is required.")


def _holding_filter(now):
    return Q(state="committed") | Q(
        state="reserved",
        expires_at__gt=now,
    )


def _policy_permits_product(policy, product_type, product_key):
    if product_type == "course":
        return policy.course_permissions.filter(
            course_key=product_key,
        ).exists()

    return policy.program_permissions.filter(
        program_code=product_key,
    ).exists()


def _grant_for_inventory(user, inventory, now):
    if inventory.audience == "public":
        return None

    if not user or not getattr(user, "is_authenticated", False):
        return None

    queryset = (
        OrganizationAccessGrant.objects.filter(
            user=user,
            organization=inventory.organization,
            active=True,
            organization__active=True,
            access_policy__active=True,
            valid_from__lte=now,
        )
        .select_related("organization", "access_policy")
        .order_by("id")
    )

    if inventory.access_policy_id:
        queryset = queryset.filter(
            access_policy=inventory.access_policy,
        )

    for grant in queryset:
        if not grant.is_active_now(now):
            continue

        if _policy_permits_product(
            grant.access_policy,
            inventory.product_type,
            inventory.product_key,
        ):
            return grant

    return None


def _active_inventories(product_type, product_key, now):
    queryset = (
        EnrollmentInventory.objects.filter(
            product_type=product_type,
            product_key=product_key,
            active=True,
            campaign__active=True,
        )
        .select_related(
            "campaign",
            "organization",
            "access_policy",
        )
        .order_by("campaign__priority", "id")
    )

    inventories = [
        inventory
        for inventory in queryset
        if inventory.campaign.is_active_now(now)
    ]

    return sorted(
        inventories,
        key=lambda inventory: (
            inventory.campaign.priority,
            0 if inventory.audience == "organization" else 1,
            inventory.pk,
        ),
    )


def _select_inventory(user, product_type, product_key, now):
    inventories = _active_inventories(
        product_type,
        product_key,
        now,
    )

    if not inventories:
        return None, None

    for inventory in inventories:
        if inventory.audience == "public":
            return inventory, None

        grant = _grant_for_inventory(user, inventory, now)

        if grant:
            return inventory, grant

    raise PromotionAccessDenied(
        "The learner is not eligible for this enrollment inventory."
    )


def _expire_inventory_reservations(inventory, now):
    return EnrollmentReservation.objects.filter(
        inventory=inventory,
        state="reserved",
        expires_at__lte=now,
    ).update(
        state="expired",
        released_at=now,
        modified=now,
    )


def _holding_count(inventory, now):
    return EnrollmentReservation.objects.filter(
        _holding_filter(now),
        inventory=inventory,
    ).count()


def _select_offer(inventory, now):
    offers = (
        PromotionOffer.objects.filter(
            inventory=inventory,
            active=True,
        )
        .select_related("inventory", "inventory__campaign")
        .order_by("priority", "id")
    )

    for offer in offers:
        if not offer.is_active_now(now):
            continue

        if offer.tier_limit is None:
            return offer

        allocated = EnrollmentReservation.objects.filter(
            _holding_filter(now),
            offer=offer,
        ).count()

        if allocated < offer.tier_limit:
            return offer

    raise PromotionCapacityExceeded(
        "No configured promotion offer has remaining capacity."
    )


def quote_product_offer(
    user,
    product_type,
    product_key,
    now=None,
):
    """Return the currently applicable offer without reserving a seat."""

    _validate_product(product_type, product_key)
    now = now or timezone.now()

    inventory, grant = _select_inventory(
        user,
        product_type,
        product_key,
        now,
    )

    if inventory is None:
        return None

    _expire_inventory_reservations(inventory, now)

    allocated = _holding_count(inventory, now)

    if (
        inventory.capacity is not None
        and allocated >= inventory.capacity
    ):
        raise PromotionCapacityExceeded(
            "No enrollment capacity remains."
        )

    offer = _select_offer(inventory, now)

    capacity_remaining = None

    if inventory.capacity is not None:
        capacity_remaining = max(
            inventory.capacity - allocated,
            0,
        )

    return {
        "campaign_key": inventory.campaign.key,
        "inventory_id": inventory.pk,
        "product_type": inventory.product_type,
        "product_key": inventory.product_key,
        "audience": inventory.audience,
        "organization_code": (
            inventory.organization.code
            if inventory.organization_id
            else None
        ),
        "access_policy_key": (
            inventory.access_policy.key
            if inventory.access_policy_id
            else None
        ),
        "offer_id": offer.pk,
        "offer_name": offer.name,
        "discount_percent": offer.discount_percent,
        "discount_amount": offer.discount_amount,
        "currency": offer.currency,
        "capacity_remaining": capacity_remaining,
        "organization_access_grant_id": (
            grant.pk if grant else None
        ),
    }


@transaction.atomic
def reserve_enrollment(
    user,
    product_type,
    product_key,
    source,
    reservation_ttl=DEFAULT_RESERVATION_TTL,
    now=None,
):
    """Atomically reserve a seat and the first available discount tier."""

    _validate_product(product_type, product_key)

    if not user or not getattr(user, "is_authenticated", False):
        raise PromotionAccessDenied(
            "Authentication is required to reserve enrollment."
        )

    if source not in dict(EnrollmentReservation.SOURCE_CHOICES):
        raise PromotionError("Invalid reservation source.")

    if reservation_ttl <= timedelta(0):
        raise PromotionError("reservation_ttl must be positive.")

    now = now or timezone.now()

    selected, grant = _select_inventory(
        user,
        product_type,
        product_key,
        now,
    )

    if selected is None:
        return None, False

    inventory = (
        EnrollmentInventory.objects.select_for_update()
        .select_related(
            "campaign",
            "organization",
            "access_policy",
        )
        .get(pk=selected.pk)
    )

    if not inventory.active or not inventory.campaign.is_active_now(now):
        raise PromotionUnavailable(
            "The enrollment inventory is no longer active."
        )

    if inventory.audience == "organization":
        grant = _grant_for_inventory(user, inventory, now)

        if grant is None:
            raise PromotionAccessDenied(
                "Organization access is not active for this product."
            )

    _expire_inventory_reservations(inventory, now)

    existing = (
        EnrollmentReservation.objects.select_for_update()
        .filter(
            inventory=inventory,
            user=user,
        )
        .first()
    )

    if existing and existing.is_holding_seat(now):
        return existing, False

    allocated = _holding_count(inventory, now)

    if (
        inventory.capacity is not None
        and allocated >= inventory.capacity
    ):
        raise PromotionCapacityExceeded(
            "No enrollment capacity remains."
        )

    offer = _select_offer(inventory, now)
    expires_at = now + reservation_ttl

    values = {
        "offer": offer,
        "organization_access_grant": grant,
        "state": "reserved",
        "source": source,
        "expires_at": expires_at,
        "discount_percent": offer.discount_percent,
        "discount_amount": offer.discount_amount,
        "currency": offer.currency,
        "enrollment_reference": "",
        "committed_at": None,
        "released_at": None,
    }

    if existing:
        for field, value in values.items():
            setattr(existing, field, value)

        existing.save()
        return existing, False

    reservation = EnrollmentReservation.objects.create(
        inventory=inventory,
        user=user,
        **values,
    )

    return reservation, True


def commit_enrollment(
    reservation_id,
    enrollment_reference="",
    user=None,
    now=None,
):
    """Convert a temporary reservation into a consumed enrollment seat."""

    now = now or timezone.now()
    expired = False

    with transaction.atomic():
        reservation = (
            EnrollmentReservation.objects.select_for_update()
            .select_related("inventory")
            .get(pk=reservation_id)
        )

        if user is not None and reservation.user_id != user.pk:
            raise PromotionAccessDenied(
                "The reservation belongs to another learner."
            )

        if reservation.state == "committed":
            return reservation, False

        if reservation.state != "reserved":
            raise ReservationStateError(
                f"Cannot commit a {reservation.state} reservation."
            )

        if (
            reservation.expires_at is None
            or reservation.expires_at <= now
        ):
            reservation.state = "expired"
            reservation.released_at = now
            reservation.save(
                update_fields=(
                    "state",
                    "released_at",
                    "modified",
                )
            )
            expired = True

        else:
            reservation.state = "committed"
            reservation.committed_at = now
            reservation.expires_at = None
            reservation.enrollment_reference = str(
                enrollment_reference or ""
            )

            reservation.save(
                update_fields=(
                    "state",
                    "committed_at",
                    "expires_at",
                    "enrollment_reference",
                    "modified",
                )
            )

    if expired:
        raise ReservationStateError(
            "The enrollment reservation has expired."
        )

    return reservation, True


@transaction.atomic
def release_enrollment(
    reservation_id,
    user=None,
    force=False,
    now=None,
):
    """Release a reservation or committed seat when policy permits."""

    now = now or timezone.now()

    reservation = (
        EnrollmentReservation.objects.select_for_update()
        .select_related("inventory")
        .get(pk=reservation_id)
    )

    if user is not None and reservation.user_id != user.pk:
        raise PromotionAccessDenied(
            "The reservation belongs to another learner."
        )

    if reservation.state in {"released", "expired"}:
        return reservation, False

    if (
        reservation.state == "committed"
        and not reservation.inventory.release_on_unenrollment
        and not force
    ):
        return reservation, False

    reservation.state = "released"
    reservation.released_at = now
    reservation.expires_at = None

    reservation.save(
        update_fields=(
            "state",
            "released_at",
            "expires_at",
            "modified",
        )
    )

    return reservation, True


@transaction.atomic
def expire_reservations(now=None):
    """Expire all elapsed temporary reservations."""

    now = now or timezone.now()

    reservations = list(
        EnrollmentReservation.objects.select_for_update().filter(
            state="reserved",
            expires_at__lte=now,
        )
    )

    for reservation in reservations:
        reservation.state = "expired"
        reservation.released_at = now
        reservation.save(
            update_fields=(
                "state",
                "released_at",
                "modified",
            )
        )

    return len(reservations)

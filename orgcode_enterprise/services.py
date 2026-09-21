import hashlib

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orgcode_enterprise.models import (
    EnterpriseLearnerProfile,
    OrgCode,
    OrgCodeUsage,
    OrganizationAccessGrant,
    OrganizationMembership,
)


GENERIC_INVALID_MESSAGE = "Organization code is invalid or unavailable."
_DUMMY_CODE_HASH = make_password("orgcode-enterprise-dummy-value")


class InvalidOrgCode(ValueError):
    pass


def normalize_code(raw_code):
    return "".join(str(raw_code or "").strip().upper().split())


def code_prefix(raw_code):
    normalized = normalize_code(raw_code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _find_code(raw_code):
    normalized = normalize_code(raw_code)
    if not normalized or len(normalized) > 128:
        check_password(normalized, _DUMMY_CODE_HASH)
        raise InvalidOrgCode(GENERIC_INVALID_MESSAGE)

    candidates = OrgCode.objects.select_related("organization", "access_policy").filter(
        code_prefix=code_prefix(normalized)
    )
    for candidate in candidates:
        if candidate.matches_code(normalized):
            return candidate

    check_password(normalized, _DUMMY_CODE_HASH)
    raise InvalidOrgCode(GENERIC_INVALID_MESSAGE)


def _latest_start(now, *values):
    return max(value for value in (now, *values) if value is not None)


def _earliest_end(*values):
    candidates = [value for value in values if value is not None]
    return min(candidates) if candidates else None


@transaction.atomic
def redeem_org_code(user, raw_code):
    """Redeem once, then return the same durable grant on safe retries."""

    matched = _find_code(raw_code)
    org_code = (
        OrgCode.objects.select_for_update()
        .select_related("organization", "access_policy")
        .get(pk=matched.pk)
    )
    now = timezone.now()

    existing = OrganizationAccessGrant.objects.filter(
        user=user,
        organization=org_code.organization,
        access_policy=org_code.access_policy,
    ).first()
    if existing and existing.is_active_now(now):
        return existing, False

    valid, _message = org_code.is_valid(user=user, now=now)
    if not valid:
        raise InvalidOrgCode(GENERIC_INVALID_MESSAGE)

    profile, _ = EnterpriseLearnerProfile.objects.get_or_create(user=user)
    membership, _ = OrganizationMembership.objects.get_or_create(
        profile=profile,
        organization=org_code.organization,
        defaults={"active": True},
    )
    if not membership.active:
        membership.active = True
        membership.save(update_fields=("active", "modified"))

    policy = org_code.access_policy
    grant_values = {
        "source_code": org_code,
        "active": True,
        "valid_from": _latest_start(now, org_code.valid_from, policy.valid_from),
        "valid_until": _earliest_end(org_code.valid_until, policy.valid_until),
        "discount_percent": policy.discount_percent,
        "discount_amount": policy.discount_amount,
        "currency": policy.currency,
    }
    grant, created = OrganizationAccessGrant.objects.update_or_create(
        user=user,
        organization=org_code.organization,
        access_policy=policy,
        defaults=grant_values,
    )

    if created:
        OrgCodeUsage.objects.get_or_create(user=user, code=org_code)
        OrgCode.objects.filter(pk=org_code.pk).update(times_used=F("times_used") + 1)

    return grant, created


def active_grants_for_user(user):
    now = timezone.now()
    queryset = (
        OrganizationAccessGrant.objects.filter(
            user=user,
            active=True,
            organization__active=True,
            access_policy__active=True,
            valid_from__lte=now,
        )
        .select_related("organization", "access_policy")
        .prefetch_related(
            "access_policy__course_permissions",
            "access_policy__program_permissions",
        )
    )
    return [grant for grant in queryset if grant.is_active_now(now)]


def serialize_grant(grant):
    policy = grant.access_policy
    return {
        "organization": {
            "code": grant.organization.code,
            "name": grant.organization.name,
        },
        "access_policy_key": policy.key,
        "valid_from": grant.valid_from,
        "valid_until": grant.valid_until,
        "discount": {
            "percent": grant.discount_percent,
            "amount": grant.discount_amount,
            "currency": grant.currency,
        },
        "permitted_course_keys": [item.course_key for item in policy.course_permissions.all()],
        "permitted_program_codes": [item.program_code for item in policy.program_permissions.all()],
    }


def authorize_private_product(user, access_policy_key, product_type, product_key):
    if product_type not in {"course", "program"}:
        return None
    for grant in active_grants_for_user(user):
        if grant.access_policy.key != access_policy_key:
            continue
        policy = grant.access_policy
        permitted = (
            policy.course_permissions.filter(course_key=product_key).exists()
            if product_type == "course"
            else policy.program_permissions.filter(program_code=product_key).exists()
        )
        if permitted:
            return grant
    return None

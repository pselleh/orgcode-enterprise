import hashlib

from django.contrib.auth.hashers import check_password, make_password
from django.db import migrations
from django.db.models import F
from django.utils import timezone


def _normalize_code(raw_code):
    return "".join(str(raw_code or "").strip().upper().split())


def _latest_start(now, *values):
    return max(value for value in (now, *values) if value is not None)


def _earliest_end(*values):
    candidates = [value for value in values if value is not None]
    return min(candidates) if candidates else None


def _organization_for_code(Organization, org_code):
    enterprise_uuid = org_code.enterprise_customer_uuid
    organization = Organization.objects.filter(
        enterprise_customer_uuid=enterprise_uuid
    ).first()
    if organization:
        return organization

    organization_code = f"enterprise-{enterprise_uuid}"
    organization, created = Organization.objects.get_or_create(
        code=organization_code,
        defaults={
            "name": org_code.description or f"Enterprise {enterprise_uuid}",
            "enterprise_customer_uuid": enterprise_uuid,
            "active": org_code.active,
        },
    )
    if not created:
        if organization.enterprise_customer_uuid not in (None, enterprise_uuid):
            raise RuntimeError(
                "An organization code collision prevents safe legacy-code migration."
            )
        organization.enterprise_customer_uuid = enterprise_uuid
        organization.save(update_fields=("enterprise_customer_uuid", "modified"))
    return organization


def _create_grant(
    *,
    Grant,
    Membership,
    profile,
    organization,
    org_code,
    policy,
    start,
):
    Membership.objects.get_or_create(
        profile=profile,
        organization=organization,
        defaults={"active": True},
    )
    Grant.objects.get_or_create(
        user_id=profile.user_id,
        organization=organization,
        access_policy=policy,
        defaults={
            "source_code": org_code,
            "active": org_code.active,
            "valid_from": start,
            "valid_until": _earliest_end(org_code.valid_until, policy.valid_until),
            "discount_percent": policy.discount_percent,
            "discount_amount": policy.discount_amount,
            "currency": policy.currency,
        },
    )


def migrate_legacy_codes(apps, schema_editor):
    AccessPolicy = apps.get_model("orgcode_enterprise", "AccessPolicy")
    CoursePermission = apps.get_model(
        "orgcode_enterprise", "AccessPolicyCoursePermission"
    )
    ProgramPermission = apps.get_model(
        "orgcode_enterprise", "AccessPolicyProgramPermission"
    )
    Organization = apps.get_model("orgcode_enterprise", "Organization")
    Profile = apps.get_model("orgcode_enterprise", "EnterpriseLearnerProfile")
    Membership = apps.get_model("orgcode_enterprise", "OrganizationMembership")
    Grant = apps.get_model("orgcode_enterprise", "OrganizationAccessGrant")
    OrgCode = apps.get_model("orgcode_enterprise", "OrgCode")
    Usage = apps.get_model("orgcode_enterprise", "OrgCodeUsage")

    now = timezone.now()
    codes_by_normalized_value = {}

    for org_code in OrgCode.objects.all().iterator():
        normalized = _normalize_code(org_code.code)
        if not normalized:
            normalized = f"DISABLED-LEGACY-{org_code.pk}"
            org_code.active = False
        if normalized in codes_by_normalized_value:
            raise RuntimeError(
                "Two legacy organization codes normalize to the same value."
            )

        organization = _organization_for_code(Organization, org_code)
        policy, _ = AccessPolicy.objects.get_or_create(
            key=f"legacy-orgcode-{org_code.pk}",
            defaults={
                "name": org_code.description
                or f"Legacy organization-code policy {org_code.pk}",
                "active": org_code.active,
                "discount_percent": org_code.discount_percent,
                "discount_amount": org_code.discount_amount,
                "currency": "USD",
                "valid_from": org_code.valid_from,
                "valid_until": org_code.valid_until,
            },
        )
        if org_code.course_id:
            CoursePermission.objects.get_or_create(
                policy=policy,
                course_key=org_code.course_id,
            )
        if org_code.program_id:
            ProgramPermission.objects.get_or_create(
                policy=policy,
                program_code=org_code.program_id,
            )

        org_code.organization = organization
        org_code.access_policy = policy
        org_code.code_prefix = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()[:16]
        org_code.code_hash = make_password(normalized)
        org_code.save(
            update_fields=(
                "organization",
                "access_policy",
                "code_prefix",
                "code_hash",
                "active",
            )
        )
        if not check_password(normalized, org_code.code_hash):
            raise RuntimeError("A legacy organization code could not be hashed safely.")
        codes_by_normalized_value[normalized] = org_code

        for usage in Usage.objects.filter(code=org_code).iterator():
            profile, _ = Profile.objects.get_or_create(user_id=usage.user_id)
            _create_grant(
                Grant=Grant,
                Membership=Membership,
                profile=profile,
                organization=organization,
                org_code=org_code,
                policy=policy,
                start=_latest_start(
                    now,
                    usage.last_used,
                    org_code.valid_from,
                    policy.valid_from,
                ),
            )

    for profile in Profile.objects.exclude(organization_code="").iterator():
        normalized = _normalize_code(profile.organization_code)
        org_code = codes_by_normalized_value.get(normalized)
        if org_code is None:
            raise RuntimeError(
                "A legacy learner organization_code does not match a registration code."
            )
        _create_grant(
            Grant=Grant,
            Membership=Membership,
            profile=profile,
            organization=org_code.organization,
            org_code=org_code,
            policy=org_code.access_policy,
            start=_latest_start(
                now,
                org_code.valid_from,
                org_code.access_policy.valid_from,
            ),
        )
        _usage, created = Usage.objects.get_or_create(
            user_id=profile.user_id,
            code=org_code,
            defaults={"times_used": 1},
        )
        if created:
            OrgCode.objects.filter(pk=org_code.pk).update(
                times_used=F("times_used") + 1
            )

    if OrgCode.objects.filter(
        organization__isnull=True
    ).exists() or OrgCode.objects.filter(access_policy__isnull=True).exists():
        raise RuntimeError("Not all legacy organization codes were linked safely.")
    if OrgCode.objects.filter(code_hash="").exists() or OrgCode.objects.filter(
        code_prefix=""
    ).exists():
        raise RuntimeError("Not all legacy organization codes were hashed safely.")


class Migration(migrations.Migration):
    dependencies = [
        ("orgcode_enterprise", "0004_access_grants_schema"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_codes, migrations.RunPython.noop),
    ]

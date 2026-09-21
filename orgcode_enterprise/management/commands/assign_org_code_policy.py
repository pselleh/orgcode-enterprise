from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from orgcode_enterprise.models import AccessPolicy, OrgCode, OrganizationAccessGrant


class Command(BaseCommand):
    help = "Assign an existing hashed organization code and its grants to an access policy."

    def add_arguments(self, parser):
        parser.add_argument("org_code_id", type=int)
        parser.add_argument("policy_key")
        parser.add_argument("--migrate-existing-grants", action="store_true")
        parser.add_argument("--validate-only", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            org_code = OrgCode.objects.select_for_update().select_related("organization", "access_policy").get(
                pk=options["org_code_id"]
            )
        except OrgCode.DoesNotExist as exc:
            raise CommandError("Organization code ID does not exist.") from exc
        try:
            policy = AccessPolicy.objects.get(key=options["policy_key"])
        except AccessPolicy.DoesNotExist as exc:
            raise CommandError("Access policy does not exist.") from exc

        grants = OrganizationAccessGrant.objects.filter(source_code=org_code)
        conflicts = grants.filter(
            user__org_access_grants__organization=org_code.organization,
            user__org_access_grants__access_policy=policy,
        ).exclude(access_policy=policy).distinct()
        if conflicts.exists():
            raise CommandError(
                "One or more learners already have the destination policy. Resolve duplicate grants first."
            )
        if grants.exclude(access_policy=policy).exists() and not options["migrate_existing_grants"]:
            raise CommandError(
                "Existing learner grants use the old policy. Re-run with --migrate-existing-grants."
            )

        self.stdout.write(
            f"Code {org_code.pk}: {org_code.access_policy.key} -> {policy.key}; grants: {grants.count()}"
        )
        if options["validate_only"]:
            transaction.set_rollback(True)
            return

        grants.update(
            access_policy=policy,
            discount_percent=policy.discount_percent,
            discount_amount=policy.discount_amount,
            currency=policy.currency,
        )
        org_code.access_policy = policy
        org_code.save(update_fields=("access_policy", "modified"))
        self.stdout.write(self.style.SUCCESS("Organization code policy assignment completed."))

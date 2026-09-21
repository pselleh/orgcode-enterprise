import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from orgcode_enterprise.models import (
    AccessPolicy,
    AccessPolicyCoursePermission,
    AccessPolicyProgramPermission,
)


class Command(BaseCommand):
    help = "Validate or import a CBA organization-access policy manifest."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)
        parser.add_argument("--policy-key", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--discount-percent")
        parser.add_argument("--discount-amount")
        parser.add_argument("--currency", default="USD")
        parser.add_argument("--validate-only", action="store_true")

    def handle(self, *args, **options):
        try:
            payload = json.loads(options["manifest"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read a valid manifest: {exc}") from exc

        courses, programs, errors = self._validate(payload, options["policy_key"])
        discount_percent = self._decimal(options.get("discount_percent"), "discount-percent", errors)
        discount_amount = self._decimal(options.get("discount_amount"), "discount-amount", errors)
        if discount_percent is not None and discount_amount is not None:
            errors.append("Only one discount type may be supplied.")
        if discount_percent is not None and not 0 <= discount_percent <= 100:
            errors.append("discount-percent must be between 0 and 100.")
        if discount_amount is not None and discount_amount < 0:
            errors.append("discount-amount cannot be negative.")
        if errors:
            raise CommandError("Access-policy validation failed:\n- " + "\n- ".join(errors))

        self.stdout.write(
            f"Validated policy {options['policy_key']}: {len(courses)} courses, {len(programs)} programs."
        )
        if options["validate_only"]:
            return

        with transaction.atomic():
            policy, _ = AccessPolicy.objects.update_or_create(
                key=options["policy_key"],
                defaults={
                    "name": options["name"],
                    "active": True,
                    "discount_percent": discount_percent,
                    "discount_amount": discount_amount,
                    "currency": options["currency"].upper(),
                },
            )
            policy.course_permissions.all().delete()
            policy.program_permissions.all().delete()
            AccessPolicyCoursePermission.objects.bulk_create(
                [AccessPolicyCoursePermission(policy=policy, course_key=value) for value in sorted(courses)]
            )
            AccessPolicyProgramPermission.objects.bulk_create(
                [AccessPolicyProgramPermission(policy=policy, program_code=value) for value in sorted(programs)]
            )
        self.stdout.write(self.style.SUCCESS(f"Imported access policy {policy.key}."))

    def _decimal(self, value, name, errors):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation:
            errors.append(f"{name} must be a decimal value.")
            return None

    def _validate(self, payload, policy_key):
        errors = []
        courses = set()
        programs = set()
        records = payload.get("courses", [])
        if not isinstance(records, list):
            return courses, programs, ["courses must be an array."]
        for index, record in enumerate(records, start=1):
            prefix = f"courses[{index}]"
            scope = record.get("access_scope")
            key = record.get("access_policy_key", "")
            if scope == "organization_code":
                if key != policy_key:
                    errors.append(f"{prefix}.access_policy_key must equal {policy_key!r}.")
                if not record.get("course_key"):
                    errors.append(f"{prefix}.course_key is required.")
                else:
                    courses.add(record["course_key"])
            elif key:
                errors.append(f"{prefix}.access_policy_key must be empty for {scope!r} access.")
        for index, record in enumerate(payload.get("programs", []), start=1):
            prefix = f"programs[{index}]"
            if record.get("access_scope") != "organization_code":
                continue
            if record.get("access_policy_key") != policy_key:
                errors.append(f"{prefix}.access_policy_key must equal {policy_key!r}.")
            if not record.get("program_code"):
                errors.append(f"{prefix}.program_code is required.")
            else:
                programs.add(record["program_code"])
        if not courses and not programs:
            errors.append("The policy contains no organization-code courses or programs.")
        return courses, programs, errors

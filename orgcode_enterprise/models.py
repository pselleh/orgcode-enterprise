from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    enterprise_customer_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    requires_accreditation_fields = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class AccessPolicy(models.Model):
    """Non-secret policy shared with Discovery through ``key``."""

    key = models.SlugField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)

    def clean(self):
        if self.discount_percent is not None and self.discount_amount is not None:
            raise ValidationError("Only one discount type may be configured.")
        if self.discount_percent is not None and not 0 <= self.discount_percent <= 100:
            raise ValidationError("discount_percent must be between 0 and 100.")
        if self.discount_amount is not None and self.discount_amount < 0:
            raise ValidationError("discount_amount cannot be negative.")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValidationError("valid_from must be before valid_until.")

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_active_now(self, now=None):
        now = now or timezone.now()
        return (
            self.active
            and (not self.valid_from or now >= self.valid_from)
            and (not self.valid_until or now <= self.valid_until)
        )

    def __str__(self):
        return f"{self.key}: {self.name}"


class AccessPolicyCoursePermission(models.Model):
    policy = models.ForeignKey(AccessPolicy, on_delete=models.CASCADE, related_name="course_permissions")
    course_key = models.CharField(max_length=255)

    class Meta:
        ordering = ("course_key",)
        constraints = [
            models.UniqueConstraint(fields=("policy", "course_key"), name="orgcode_unique_policy_course")
        ]

    def __str__(self):
        return f"{self.policy.key}: {self.course_key}"


class AccessPolicyProgramPermission(models.Model):
    policy = models.ForeignKey(AccessPolicy, on_delete=models.CASCADE, related_name="program_permissions")
    program_code = models.CharField(max_length=128)

    class Meta:
        ordering = ("program_code",)
        constraints = [
            models.UniqueConstraint(fields=("policy", "program_code"), name="orgcode_unique_policy_program")
        ]

    def __str__(self):
        return f"{self.policy.key}: {self.program_code}"


class OrgCode(models.Model):
    """Hashed registration code that grants an organization access policy."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="registration_codes",
    )
    access_policy = models.ForeignKey(
        AccessPolicy,
        on_delete=models.PROTECT,
        related_name="registration_codes",
    )
    enterprise_customer_uuid = models.UUIDField(db_index=True)
    code_hash = models.CharField(max_length=255)
    code_prefix = models.CharField(max_length=16, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("organization__name", "id")

    def clean(self):
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValidationError("valid_from must be before valid_until.")
        if self.organization_id and self.enterprise_customer_uuid:
            org_uuid = self.organization.enterprise_customer_uuid
            if org_uuid and org_uuid != self.enterprise_customer_uuid:
                raise ValidationError("enterprise_customer_uuid must match the organization.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def set_code(self, raw_code):
        from orgcode_enterprise.services import code_prefix, normalize_code

        normalized = normalize_code(raw_code)
        if not normalized:
            raise ValidationError("Organization code cannot be empty.")
        self.code_prefix = code_prefix(normalized)
        self.code_hash = make_password(normalized)

    def matches_code(self, raw_code):
        from orgcode_enterprise.services import normalize_code

        return check_password(normalize_code(raw_code), self.code_hash)

    def is_valid(self, user=None, now=None):
        now = now or timezone.now()
        if not self.active or not self.organization.active:
            return False, "Organization code is not available."
        if not self.access_policy.is_active_now(now):
            return False, "Organization code is not available."
        if self.valid_from and now < self.valid_from:
            return False, "Organization code is not available."
        if self.valid_until and now > self.valid_until:
            return False, "Organization code is not available."
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False, "Organization code is not available."
        if user and self.max_uses_per_user is not None:
            count = OrgCodeUsage.objects.filter(user=user, code=self).count()
            if count >= self.max_uses_per_user:
                return False, "Organization code is not available."
        return True, "Valid"

    def __str__(self):
        return f"{self.organization.code} / {self.access_policy.key} / …{self.code_prefix[-4:]}"


class OrgCodeUsage(models.Model):
    """One audit record per user/code redemption; redemption is idempotent."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orgcode_usages")
    code = models.ForeignKey(OrgCode, on_delete=models.PROTECT, related_name="usages")
    times_used = models.PositiveIntegerField(default=1)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "code"), name="orgcode_unique_user_code_usage")
        ]

    def __str__(self):
        return f"{self.user} -> {self.code_id}"


class EnterpriseLearnerProfile(models.Model):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("faculty", "Faculty"),
        ("staff", "Staff"),
        ("admin", "Administrator"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enterprise_profile")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="student", db_index=True)
    honorific = models.CharField(max_length=32, blank=True)
    middle_initial = models.CharField(max_length=1, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=32, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    alternate_phone_number = models.CharField(max_length=32, blank=True)
    timezone = models.CharField(max_length=64, default="America/New_York")
    student_identifier = models.CharField(max_length=64, blank=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Enterprise Profile"


class OrganizationMembership(models.Model):
    profile = models.ForeignKey(EnterpriseLearnerProfile, on_delete=models.CASCADE, related_name="organization_memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("profile", "organization"), name="orgcode_unique_profile_org")]

    def __str__(self):
        return f"{self.profile.user.username} - {self.organization.code}"


class OrganizationAccessGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="org_access_grants")
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="access_grants")
    access_policy = models.ForeignKey(AccessPolicy, on_delete=models.PROTECT, related_name="access_grants")
    source_code = models.ForeignKey(OrgCode, on_delete=models.PROTECT, related_name="access_grants")
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("access_policy__key", "id")
        constraints = [
            models.UniqueConstraint(fields=("user", "organization", "access_policy"), name="orgcode_unique_user_org_policy")
        ]

    def is_active_now(self, now=None):
        now = now or timezone.now()
        return (
            self.active
            and self.organization.active
            and self.access_policy.is_active_now(now)
            and now >= self.valid_from
            and (not self.valid_until or now <= self.valid_until)
        )

    def __str__(self):
        return f"{self.user} / {self.access_policy.key}"


class LearnerAddress(models.Model):
    profile = models.OneToOneField(EnterpriseLearnerProfile, on_delete=models.CASCADE, related_name="address")
    country = models.CharField(max_length=64, default="United States")
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.profile.user.username} Address"


class LearnerAccreditationRecord(models.Model):
    ETHNICITY_CHOICES = [("hispanic_or_latino", "Hispanic or Latino"), ("not_hispanic_or_latino", "Not Hispanic or Latino")]
    RACE_CHOICES = [
        ("american_indian_or_alaska_native", "American Indian or Alaska Native"),
        ("asian", "Asian"), ("black_or_african_american", "Black or African American"),
        ("native_hawaiian_or_other_pacific_islander", "Native Hawaiian or Other Pacific Islander"),
        ("white", "White"), ("some_other_race", "Some Other Race"), ("two_or_more_races", "Two or More Races"),
    ]
    VETERAN_STATUS_CHOICES = [
        ("non_veteran", "Non Veteran"), ("veteran", "Veteran"),
        ("disabled_veteran", "Disabled Veteran"), ("spouse_of_veteran", "Spouse of a Veteran"),
    ]
    BRANCH_CHOICES = [
        ("army", "Army"), ("marine_corps", "Marine Corps"), ("navy", "Navy"),
        ("air_force", "Air Force"), ("space_force", "Space Force"), ("coast_guard", "Coast Guard"),
    ]
    CITIZENSHIP_CHOICES = [
        ("united_states", "United States"), ("permanent_resident", "Permanent Resident"),
        ("not_us_citizen_or_permanent_resident", "Not a United States Citizen or Permanent Resident"),
    ]
    EDUCATION_LEVEL_CHOICES = [
        ("less_than_high_school", "Less than High School"),
        ("high_school_graduate_or_ged", "High School Graduate or GED"),
        ("some_college_or_technical_training", "Some College or Technical Training"),
        ("college_graduate_or_higher", "College Graduate or Higher"),
    ]
    ENGLISH_PROFICIENCY_CHOICES = [
        ("native_speaker", "Native speaker"), ("fluent", "Fluent (can speak, read, and write easily)"),
        ("conversational", "Conversational (can handle everyday situations)"),
        ("basic", "Basic (know some words and phrases)"), ("none", "No English proficiency"),
    ]
    profile = models.OneToOneField(EnterpriseLearnerProfile, on_delete=models.CASCADE, related_name="accreditation")
    ethnicity = models.CharField(max_length=64, choices=ETHNICITY_CHOICES, blank=True)
    race = models.CharField(max_length=64, choices=RACE_CHOICES, blank=True)
    veteran_status = models.CharField(max_length=64, choices=VETERAN_STATUS_CHOICES, default="non_veteran", db_index=True)
    branch_of_service = models.CharField(max_length=64, choices=BRANCH_CHOICES, blank=True)
    citizenship = models.CharField(max_length=100, choices=CITIZENSHIP_CHOICES, blank=True)
    education_level = models.CharField(max_length=100, choices=EDUCATION_LEVEL_CHOICES, blank=True)
    english_proficiency = models.CharField(max_length=100, choices=ENGLISH_PROFICIENCY_CHOICES, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)

    def clean(self):
        if self.veteran_status in {"veteran", "disabled_veteran"} and not self.branch_of_service:
            raise ValidationError("Branch of service is required for Veteran or Disabled Veteran status.")

    def __str__(self):
        return f"{self.profile.user.username} Accreditation Record"


class CertificateProgram(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="certificate_programs")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    requires_accreditation_fields = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class CertificateProgramEnrollment(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("completed", "Completed"), ("withdrawn", "Withdrawn")]
    profile = models.ForeignKey(EnterpriseLearnerProfile, on_delete=models.CASCADE, related_name="certificate_program_enrollments")
    program = models.ForeignKey(CertificateProgram, on_delete=models.CASCADE, related_name="learner_enrollments")
    cohort = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="active")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("profile", "program"), name="orgcode_unique_profile_program")]

    def __str__(self):
        return f"{self.profile.user.username} - {self.program.code}"


# Promotion and enrollment-inventory models are kept separately to keep this
# established models module manageable. Importing them registers the models
# with the orgcode_enterprise Django application.
from orgcode_enterprise.promotion_models import (  # noqa: E402, F401
    EnrollmentInventory,
    EnrollmentReservation,
    PromotionCampaign,
    PromotionOffer,
)

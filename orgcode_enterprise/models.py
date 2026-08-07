from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

User = get_user_model()


class OrgCode(models.Model):
    """
    Organization access code with support for:
    - enterprise linkage
    - discounts
    - expiration
    - total usage limits
    - per-user limits
    """

    # ------------------------
    # Core
    # ------------------------
    code = models.CharField(max_length=50, unique=True, db_index=True)
    enterprise_customer_uuid = models.UUIDField(db_index=True)

    description = models.CharField(max_length=255, blank=True)

    # ------------------------
    # Activation
    # ------------------------
    active = models.BooleanField(default=True)

    # ------------------------
    # Discount (only ONE should be used)
    # ------------------------
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # ------------------------
    # Usage limits
    # ------------------------
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(null=True, blank=True)

    # ------------------------
    # Validity window
    # ------------------------
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    # ------------------------
    # Targeting (optional)
    # ------------------------
    course_id = models.CharField(max_length=255, null=True, blank=True)
    program_id = models.CharField(max_length=255, null=True, blank=True)

    # ------------------------
    # Audit
    # ------------------------
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    # ------------------------
    # VALIDATION
    # ------------------------
    def clean(self):
        # Only one discount type allowed
        if self.discount_percent and self.discount_amount:
            raise ValidationError(
                "Only one of discount_percent or discount_amount can be set."
            )

        # Validate date range
        if self.valid_from and self.valid_until:
            if self.valid_from > self.valid_until:
                raise ValidationError("valid_from must be before valid_until.")

    def save(self, *args, **kwargs):
        self.full_clean()  # enforce validation
        super().save(*args, **kwargs)

    # ------------------------
    # BUSINESS LOGIC
    # ------------------------
    def is_valid(self, user=None):
        if not self.active:
            return False, "Code is inactive"

        now = timezone.now()

        if self.valid_from and now < self.valid_from:
            return False, "Code not yet valid"

        if self.valid_until and now > self.valid_until:
            return False, "Code expired"

        if self.usage_limit and self.times_used >= self.usage_limit:
            return False, "Usage limit reached"

        if user and self.max_uses_per_user:
            usage = OrgCodeUsage.objects.filter(user=user, code=self).first()
            if usage and usage.times_used >= self.max_uses_per_user:
                return False, "User usage limit reached"

        return True, "Valid"

    def apply_to_user(self, user):
        valid, message = self.is_valid(user)

        if not valid:
            return False, message

        usage, _ = OrgCodeUsage.objects.get_or_create(
            user=user,
            code=self
        )

        usage.times_used += 1
        usage.save()

        self.times_used += 1
        self.save()

        return True, "Code applied"

    def __str__(self):
        return f"{self.code} (active={self.active})"


class OrgCodeUsage(models.Model):
    """
    Tracks usage of org codes per user
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orgcode_usages",
    )


    code = models.ForeignKey(
        OrgCode,
        on_delete=models.CASCADE,
        related_name="usages",
    )

    times_used = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "code")

    def __str__(self):
        return f"{self.user} -> {self.code} ({self.times_used})"


class EnterpriseLearnerProfile(models.Model):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("faculty", "Faculty"),
        ("staff", "Staff"),
        ("admin", "Administrator"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="enterprise_profile",
    )

    role = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        default="student",
        db_index=True,
    )

    honorific = models.CharField(max_length=32, blank=True)
    middle_initial = models.CharField(max_length=1, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=32, blank=True)

    phone_number = models.CharField(max_length=32, blank=True)
    alternate_phone_number = models.CharField(max_length=32, blank=True)

    timezone = models.CharField(max_length=64, default="America/New_York")

    student_identifier = models.CharField(max_length=64, blank=True, db_index=True)
    organization_code = models.CharField(max_length=64, blank=True, db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Enterprise Profile"


class LearnerAddress(models.Model):
    profile = models.OneToOneField(
        EnterpriseLearnerProfile,
        on_delete=models.CASCADE,
        related_name="address",
    )

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
    ETHNICITY_CHOICES = [
        ("hispanic_or_latino", "Hispanic or Latino"),
        ("not_hispanic_or_latino", "Not Hispanic or Latino"),
    ]

    RACE_CHOICES = [
        ("american_indian_or_alaska_native", "American Indian or Alaska Native"),
        ("asian", "Asian"),
        ("black_or_african_american", "Black or African American"),
        ("native_hawaiian_or_other_pacific_islander", "Native Hawaiian or Other Pacific Islander"),
        ("white", "White"),
        ("some_other_race", "Some Other Race"),
        ("two_or_more_races", "Two or More Races"),
    ]

    VETERAN_STATUS_CHOICES = [
        ("non_veteran", "Non Veteran"),
        ("veteran", "Veteran"),
        ("disabled_veteran", "Disabled Veteran"),
        ("spouse_of_veteran", "Spouse of a Veteran"),
    ]

    BRANCH_CHOICES = [
        ("army", "Army"),
        ("marine_corps", "Marine Corps"),
        ("navy", "Navy"),
        ("air_force", "Air Force"),
        ("space_force", "Space Force"),
        ("coast_guard", "Coast Guard"),
    ]

    CITIZENSHIP_CHOICES = [
        ("united_states", "United States"),
        ("permanent_resident", "Permanent Resident"),
        ("not_us_citizen_or_permanent_resident", "Not a United States Citizen or Permanent Resident"),
    ]

    EDUCATION_LEVEL_CHOICES = [
        ("less_than_high_school", "Less than High School"),
        ("high_school_graduate_or_ged", "High School Graduate or GED"),
        ("some_college_or_technical_training", "Some College or Technical Training"),
        ("college_graduate_or_higher", "College Graduate or Higher"),
    ]

    ENGLISH_PROFICIENCY_CHOICES = [
        ("native_speaker", "Native speaker"),
        ("fluent", "Fluent (can speak, read, and write easily)"),
        ("conversational", "Conversational (can handle everyday situations)"),
        ("basic", "Basic (know some words and phrases)"),
        ("none", "No English proficiency"),
    ]

    profile = models.OneToOneField(
        EnterpriseLearnerProfile,
        on_delete=models.CASCADE,
        related_name="accreditation",
    )

    ethnicity = models.CharField(max_length=64, choices=ETHNICITY_CHOICES, blank=True)
    race = models.CharField(max_length=64, choices=RACE_CHOICES, blank=True)

    veteran_status = models.CharField(
        max_length=64,
        choices=VETERAN_STATUS_CHOICES,
        default="non_veteran",
        db_index=True,
    )

    branch_of_service = models.CharField(
        max_length=64,
        choices=BRANCH_CHOICES,
        blank=True,
    )

    citizenship = models.CharField(max_length=100, choices=CITIZENSHIP_CHOICES, blank=True)
    education_level = models.CharField(max_length=100, choices=EDUCATION_LEVEL_CHOICES, blank=True)
    english_proficiency = models.CharField(max_length=100, choices=ENGLISH_PROFICIENCY_CHOICES, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.veteran_status in ["veteran", "disabled_veteran"] and not self.branch_of_service:
            raise ValidationError(
                "Branch of service is required for Veteran or Disabled Veteran status."
            )

    def __str__(self):
        return f"{self.profile.user.username} Accreditation Record"

    class Meta:
        ordering = ["id"]


class Organization(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    requires_accreditation_fields = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class OrganizationMembership(models.Model):
    profile = models.ForeignKey(
        EnterpriseLearnerProfile,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    active = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "organization")

    def __str__(self):
        return f"{self.profile.user.username} - {self.organization.code}"


class CertificateProgram(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="certificate_programs",
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    requires_accreditation_fields = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

class CertificateProgramEnrollment(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("withdrawn", "Withdrawn"),
    ]

    profile = models.ForeignKey(
        EnterpriseLearnerProfile,
        on_delete=models.CASCADE,
        related_name="certificate_program_enrollments",
    )

    program = models.ForeignKey(
        CertificateProgram,
        on_delete=models.CASCADE,
        related_name="learner_enrollments",
    )

    cohort = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="active")

    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("profile", "program")

    def __str__(self):
        return f"{self.profile.user.username} - {self.program.code}"

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

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.ForeignKey(OrgCode, on_delete=models.CASCADE)

    times_used = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "code")

    def __str__(self):
        return f"{self.user} -> {self.code} ({self.times_used})"

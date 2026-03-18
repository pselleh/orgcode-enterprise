from django.db import models
from django.contrib.auth import get_user_model

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

    # Core
    code = models.CharField(max_length=50, unique=True)
    enterprise_customer_uuid = models.UUIDField()

    description = models.CharField(max_length=255, blank=True)

    # Activation
    active = models.BooleanField(default=True)

    # Discount
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    discount_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    # Usage limits (global)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    # Usage limits (per-user)
    max_uses_per_user = models.PositiveIntegerField(null=True, blank=True)

    # Validity window
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    # Optional targeting
    course_id = models.CharField(max_length=255, null=True, blank=True)
    program_id = models.CharField(max_length=255, null=True, blank=True)

    # Audit
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Org Code"
        verbose_name_plural = "Org Codes"

    def __str__(self):
        return self.code


class OrgCodeUsage(models.Model):
    """
    Tracks per-user usage of org codes
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.ForeignKey(OrgCode, on_delete=models.CASCADE)
    times_used = models.PositiveIntegerField(default=0)

    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "code")
        verbose_name = "Org Code Usage"
        verbose_name_plural = "Org Code Usage"

    def __str__(self):
        return f"{self.user} - {self.code} ({self.times_used})"

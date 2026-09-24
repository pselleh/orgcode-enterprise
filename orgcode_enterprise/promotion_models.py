import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PromotionCampaign(models.Model):
    """One reusable marketing or enrollment-promotion period."""

    key = models.SlugField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    external_reference = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "key")

    def clean(self):
        if (
            self.valid_from
            and self.valid_until
            and self.valid_from > self.valid_until
        ):
            raise ValidationError(
                "valid_from must be before valid_until."
            )

    def save(self, *args, **kwargs):
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


class EnrollmentInventory(models.Model):
    """Seat pool for one campaign, product and audience."""

    PRODUCT_TYPE_CHOICES = [
        ("course", "Course"),
        ("program", "Certificate Program"),
    ]

    AUDIENCE_CHOICES = [
        ("public", "Public"),
        ("organization", "Organization"),
    ]

    campaign = models.ForeignKey(
        PromotionCampaign,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    product_type = models.CharField(
        max_length=16,
        choices=PRODUCT_TYPE_CHOICES,
    )
    product_key = models.CharField(max_length=255, db_index=True)
    audience = models.CharField(
        max_length=32,
        choices=AUDIENCE_CHOICES,
        default="public",
    )
    organization = models.ForeignKey(
        "orgcode_enterprise.Organization",
        on_delete=models.PROTECT,
        related_name="promotion_inventories",
        null=True,
        blank=True,
    )
    access_policy = models.ForeignKey(
        "orgcode_enterprise.AccessPolicy",
        on_delete=models.PROTECT,
        related_name="promotion_inventories",
        null=True,
        blank=True,
    )
    scope_key = models.CharField(
        max_length=160,
        editable=False,
        db_index=True,
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    release_on_unenrollment = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "campaign__priority",
            "product_type",
            "product_key",
            "scope_key",
        )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "campaign",
                    "product_type",
                    "product_key",
                    "scope_key",
                ),
                name="orgcode_unique_campaign_inventory",
            ),
        ]

    def _build_scope_key(self):
        if self.audience == "public":
            return "public"

        organization_id = self.organization_id or "missing"
        policy_id = self.access_policy_id or "any"

        return f"organization:{organization_id}:policy:{policy_id}"

    def clean(self):
        if self.audience == "public":
            if self.organization_id or self.access_policy_id:
                raise ValidationError(
                    "Public inventory cannot specify an organization "
                    "or access policy."
                )

        elif self.audience == "organization":
            if not self.organization_id:
                raise ValidationError(
                    "Organization inventory requires an organization."
                )

        self.scope_key = self._build_scope_key()

    def save(self, *args, **kwargs):
        self.scope_key = self._build_scope_key()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.campaign.key} / {self.product_type} / "
            f"{self.product_key} / {self.scope_key}"
        )


class PromotionOffer(models.Model):
    """One discount tier within an enrollment inventory pool."""

    inventory = models.ForeignKey(
        EnrollmentInventory,
        on_delete=models.CASCADE,
        related_name="offers",
    )
    name = models.CharField(max_length=255)
    priority = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)
    tier_limit = models.PositiveIntegerField(null=True, blank=True)
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("inventory", "priority", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "priority"),
                name="orgcode_unique_inventory_offer_priority",
            ),
        ]

    def clean(self):
        if (
            self.discount_percent is not None
            and self.discount_amount is not None
        ):
            raise ValidationError(
                "Only one discount type may be configured."
            )

        if (
            self.discount_percent is not None
            and not 0 <= self.discount_percent <= 100
        ):
            raise ValidationError(
                "discount_percent must be between 0 and 100."
            )

        if (
            self.discount_amount is not None
            and self.discount_amount < 0
        ):
            raise ValidationError(
                "discount_amount cannot be negative."
            )

        if (
            self.valid_from
            and self.valid_until
            and self.valid_from > self.valid_until
        ):
            raise ValidationError(
                "valid_from must be before valid_until."
            )

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_active_now(self, now=None):
        now = now or timezone.now()

        return (
            self.active
            and self.inventory.active
            and self.inventory.campaign.is_active_now(now)
            and (not self.valid_from or now >= self.valid_from)
            and (not self.valid_until or now <= self.valid_until)
        )

    def __str__(self):
        return f"{self.inventory} / {self.name}"


class EnrollmentReservation(models.Model):
    """Auditable temporary reservation or committed enrollment seat."""

    STATE_CHOICES = [
        ("reserved", "Reserved"),
        ("committed", "Committed"),
        ("released", "Released"),
        ("expired", "Expired"),
    ]

    SOURCE_CHOICES = [
        ("course_filter", "Course Enrollment Filter"),
        ("program_api", "Program Enrollment API"),
        ("administrative", "Administrative"),
        ("reconciliation", "Reconciliation"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    inventory = models.ForeignKey(
        EnrollmentInventory,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    offer = models.ForeignKey(
        PromotionOffer,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promotion_reservations",
    )
    organization_access_grant = models.ForeignKey(
        "orgcode_enterprise.OrganizationAccessGrant",
        on_delete=models.PROTECT,
        related_name="promotion_reservations",
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=16,
        choices=STATE_CHOICES,
        default="reserved",
        db_index=True,
    )
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    enrollment_reference = models.CharField(
        max_length=255,
        blank=True,
    )
    reserved_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-reserved_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "user"),
                name="orgcode_unique_inventory_user_reservation",
            ),
        ]
        indexes = [
            models.Index(
                fields=("state", "expires_at"),
                name="orgcode_res_state_exp_idx",
            ),
            models.Index(
                fields=("user", "state"),
                name="orgcode_res_user_state_idx",
            ),
        ]

    def clean(self):
        if (
            self.offer_id
            and self.inventory_id
            and self.offer.inventory_id != self.inventory_id
        ):
            raise ValidationError(
                "The selected offer must belong to the inventory."
            )

        if (
            self.state == "reserved"
            and self.expires_at is None
        ):
            raise ValidationError(
                "A reserved seat requires expires_at."
            )

        self.currency = self.currency.upper()

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_holding_seat(self, now=None):
        now = now or timezone.now()

        return (
            self.state == "committed"
            or (
                self.state == "reserved"
                and self.expires_at is not None
                and self.expires_at > now
            )
        )

    def __str__(self):
        return (
            f"{self.user_id} / {self.inventory_id} / "
            f"{self.state}"
        )

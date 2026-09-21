from django import forms
from django.contrib import admin

from orgcode_enterprise.models import (
    AccessPolicy,
    AccessPolicyCoursePermission,
    AccessPolicyProgramPermission,
    EnterpriseLearnerProfile,
    OrgCode,
    OrgCodeUsage,
    Organization,
    OrganizationAccessGrant,
    OrganizationMembership,
)


class OrgCodeForm(forms.ModelForm):
    raw_code = forms.CharField(
        required=False,
        strip=True,
        widget=forms.PasswordInput(render_value=False),
        help_text="Required when creating a code. Leave blank when editing to keep the current code.",
    )

    class Meta:
        model = OrgCode
        exclude = ("code_hash", "code_prefix", "times_used")

    def clean_raw_code(self):
        raw_code = self.cleaned_data.get("raw_code", "")
        if not self.instance.pk and not raw_code:
            raise forms.ValidationError("A new organization code is required.")
        return raw_code

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_code = self.cleaned_data.get("raw_code")
        if raw_code:
            instance.set_code(raw_code)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CoursePermissionInline(admin.TabularInline):
    model = AccessPolicyCoursePermission
    extra = 0


class ProgramPermissionInline(admin.TabularInline):
    model = AccessPolicyProgramPermission
    extra = 0


@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "active", "discount_percent", "discount_amount", "valid_until")
    list_filter = ("active", "currency")
    search_fields = ("key", "name")
    inlines = (CoursePermissionInline, ProgramPermissionInline)


@admin.register(OrgCode)
class OrgCodeAdmin(admin.ModelAdmin):
    form = OrgCodeForm
    list_display = ("organization", "access_policy", "active", "usage_limit", "times_used", "valid_until")
    list_filter = ("active", "organization", "access_policy")
    search_fields = ("organization__name", "organization__code", "access_policy__key", "description")
    readonly_fields = ("times_used", "created", "modified")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active", "enterprise_customer_uuid")
    list_filter = ("active",)
    search_fields = ("code", "name")


@admin.register(OrganizationAccessGrant)
class OrganizationAccessGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "access_policy", "active", "valid_from", "valid_until")
    list_filter = ("active", "organization", "access_policy")
    search_fields = ("user__username", "user__email", "organization__code", "access_policy__key")
    readonly_fields = ("created", "modified")


admin.site.register(EnterpriseLearnerProfile)
admin.site.register(OrganizationMembership)
admin.site.register(OrgCodeUsage)

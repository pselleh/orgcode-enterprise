from django.contrib import admin
from .models import OrgCode

@admin.register(OrgCode)
class OrgCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "enterprise_customer_uuid", "active", "usage_limit", "times_used")
    search_fields = ("code",)

from django.contrib import admin

from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "organization", "role", "is_active"]
    list_filter = ["organization", "is_active"]
    search_fields = ["name", "email"]
    list_select_related = ["organization"]

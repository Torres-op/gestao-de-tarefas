from django.contrib import admin

from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "role", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "email"]

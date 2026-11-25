from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Organization, Profile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role"]
    list_filter = ["organization", "role"]
    search_fields = ["user__username", "user__email"]
    list_select_related = ["user", "organization"]


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Perfil na organização"


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ["username", "email", "first_name", "is_staff", "profile_organization", "profile_role"]
    list_select_related = ["profile__organization"]

    @admin.display(description="Organização")
    def profile_organization(self, user):
        profile = getattr(user, "profile", None)
        return profile.organization if profile else "—"

    @admin.display(description="Papel")
    def profile_role(self, user):
        profile = getattr(user, "profile", None)
        return profile.get_role_display() if profile else "—"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

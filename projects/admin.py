from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "due_date", "created_at"]
    search_fields = ["name", "description"]

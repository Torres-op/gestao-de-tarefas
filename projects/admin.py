from django.contrib import admin

from .models import Project, Sprint


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "start_date", "due_date", "created_at"]
    list_filter = ["organization"]
    search_fields = ["name", "description"]
    list_select_related = ["organization"]


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "start_date", "end_date"]
    list_filter = ["project__organization", "project"]
    search_fields = ["name", "goal"]
    list_select_related = ["project"]

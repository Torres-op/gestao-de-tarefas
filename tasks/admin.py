from django.contrib import admin

from .models import Subtask, Task


class SubtaskInline(admin.TabularInline):
    model = Subtask
    extra = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "assignee", "status", "due_date"]
    list_filter = ["status", "project"]
    search_fields = ["title", "description"]
    inlines = [SubtaskInline]


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ["title", "task", "is_done"]
    list_filter = ["is_done"]
    search_fields = ["title"]

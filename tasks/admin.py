from django.contrib import admin

from .models import Subtask, Task, TaskDependency


class SubtaskInline(admin.TabularInline):
    model = Subtask
    extra = 1


class TaskDependencyInline(admin.TabularInline):
    model = TaskDependency
    fk_name = "task"
    extra = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "assignee", "status", "due_date"]
    list_filter = ["status", "project"]
    search_fields = ["title", "description"]
    inlines = [SubtaskInline, TaskDependencyInline]


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ["title", "task", "is_done"]
    list_filter = ["is_done"]
    search_fields = ["title"]


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ["task", "depends_on"]
    search_fields = ["task__title", "depends_on__title"]

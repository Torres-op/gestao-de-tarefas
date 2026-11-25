from django.contrib import admin

from projects.models import Sprint

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
    list_display = ["title", "project", "sprint", "assignee", "status", "due_date"]
    list_filter = ["project__organization", "status", "project"]
    list_select_related = ["project", "sprint__project", "assignee"]
    search_fields = ["title", "description"]
    inlines = [SubtaskInline, TaskDependencyInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sprint":
            kwargs["queryset"] = Sprint.objects.select_related("project")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ["title", "task", "is_done"]
    list_filter = ["is_done"]
    search_fields = ["title"]


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ["task", "depends_on"]
    search_fields = ["task__title", "depends_on__title"]

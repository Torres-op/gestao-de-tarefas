from django.db.models import Prefetch

from .models import Task, TaskDependency


def dependencies_prefetch(prefix=""):
    return Prefetch(f"{prefix}dependencies", queryset=TaskDependency.objects.select_related("depends_on"))


def dependents_prefetch(prefix=""):
    return Prefetch(f"{prefix}dependents", queryset=TaskDependency.objects.select_related("task"))


def task_table_prefetches(lookup, *related):
    return [
        Prefetch(lookup, queryset=Task.objects.select_related(*related)),
        f"{lookup}__subtasks",
        dependencies_prefetch(f"{lookup}__"),
    ]

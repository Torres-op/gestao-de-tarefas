from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from django.utils import timezone

from projects.models import Project, Sprint

from . import metrics
from .forms import DashboardFilterForm


@dataclass
class DashboardFilters:
    start: date
    end: date
    default_period: bool
    project: Project | None = None
    sprint: Sprint | None = None

    def querystring(self):
        params = {"start": self.start.isoformat(), "end": self.end.isoformat()}
        if self.project:
            params["project"] = self.project.pk
        if self.sprint:
            params["sprint"] = self.sprint.pk
        return urlencode(params)


def parse_filters(data, organization, today=None):
    today = today or timezone.localdate()
    form = DashboardFilterForm(data, organization=organization)
    form.is_valid()
    cleaned = getattr(form, "cleaned_data", {})
    raw_start = cleaned.get("start")
    raw_end = cleaned.get("end")
    start, end = metrics.resolve_period(raw_start, raw_end, today)
    filters = DashboardFilters(
        start=start,
        end=end,
        default_period=raw_start is None and raw_end is None,
        project=cleaned.get("project"),
        sprint=cleaned.get("sprint"),
    )
    return form, filters


def scoped_tasks(organization, filters):
    return metrics.apply_filters(
        metrics.organization_tasks(organization),
        project=filters.project,
        sprint=filters.sprint,
    )


def default_burndown_sprint(organization, project=None, today=None):
    sprints = Sprint.objects.filter(project__organization=organization).select_related("project")
    if project:
        sprints = sprints.filter(project=project)
    return metrics.default_sprint(sprints, today)


def dashboard_payload(organization, filters, is_admin, today=None):
    today = today or timezone.localdate()
    tasks = scoped_tasks(organization, filters)
    sprint = filters.sprint or default_burndown_sprint(organization, filters.project, today)
    payload = {
        "period": {"start": filters.start, "end": filters.end, "default": filters.default_period},
        "filters": {
            "project": filters.project.pk if filters.project else None,
            "sprint": filters.sprint.pk if filters.sprint else None,
        },
        "kpis": metrics.kpis(tasks, filters.start, filters.end, today),
        "status_distribution": metrics.status_distribution(tasks),
        "workload": metrics.member_workload(tasks, filters.start, filters.end, today),
        "projects": metrics.project_progress(tasks, today),
        "burndown": metrics.sprint_burndown(sprint, today, tasks) if sprint else None,
    }
    if is_admin:
        payload["flow"] = metrics.flow_series(tasks, filters.start, filters.end)
        payload["velocity"] = metrics.velocity(tasks, today)
    return payload

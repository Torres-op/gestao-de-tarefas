from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.permissions import admin_required
from core.tenancy import current_organization, is_org_admin

from . import metrics
from .exports import write_tasks_csv
from .services import dashboard_payload, parse_filters, scoped_tasks

PACE_BADGES = {
    "ahead": "badge-success",
    "on_track": "badge-info",
    "behind": "badge-danger",
    "not_started": "badge-neutral",
    "empty": "badge-neutral",
}
STATE_BADGES = {
    "planned": "badge-neutral",
    "active": "badge-info",
    "finished": "badge-success",
}


def dashboard_index(request):
    organization = current_organization(request)
    today = timezone.localdate()
    form, filters = parse_filters(request.GET, organization, today)
    is_admin = is_org_admin(request.user)
    data = dashboard_payload(organization, filters, is_admin, today)
    status_total = sum(item["total"] for item in data["status_distribution"])
    flow = data.get("flow")
    velocity = data.get("velocity")
    context = {
        "form": form,
        "filters": filters,
        "today": today,
        "data": data,
        "kpis": data["kpis"],
        "on_time_note": on_time_note(data["kpis"]),
        "status_distribution": data["status_distribution"],
        "status_total": status_total,
        "workload": data["workload"],
        "projects": data["projects"],
        "burndown": data["burndown"],
        "burndown_rows": burndown_rows(data["burndown"]),
        "pace_badge": PACE_BADGES.get(data["burndown"]["status"]) if data["burndown"] else "",
        "state_badge": STATE_BADGES.get(data["burndown"]["sprint"]["state"]) if data["burndown"] else "",
        "flow": flow,
        "flow_rows": flow_rows(flow),
        "flow_has_data": bool(flow and (any(flow["created"]) or any(flow["completed"]))),
        "velocity": velocity,
        "velocity_rows": velocity["sprints"] if velocity else [],
        "show_admin_blocks": is_admin,
        "export_query": filters.querystring(),
        "default_period_days": metrics.DEFAULT_PERIOD_DAYS,
    }
    return render(request, "dashboard/index.html", context)


def on_time_note(kpis):
    if not kpis["due_completed"]:
        return "nenhuma concluída com prazo definido"
    return f"{kpis['on_time']} de {kpis['due_completed']} concluídas com prazo"


def burndown_rows(burndown):
    if not burndown:
        return []
    return [
        {"label": label, "ideal": ideal, "remaining": remaining, "completed": completed}
        for label, ideal, remaining, completed in zip(
            burndown["labels"], burndown["ideal"], burndown["remaining"], burndown["completed"]
        )
    ]


def flow_rows(flow):
    if not flow:
        return []
    return [
        {"label": label, "created": created, "completed": completed}
        for label, created, completed in zip(flow["labels"], flow["created"], flow["completed"])
    ]


@admin_required
def export_csv(request):
    organization = current_organization(request)
    today = timezone.localdate()
    _, filters = parse_filters(request.GET, organization, today)
    tasks = metrics.task_report(scoped_tasks(organization, filters), filters.start, filters.end)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="grello-tarefas-{today:%Y-%m-%d}.csv"'
    write_tasks_csv(response, tasks)
    return response

from datetime import date, timedelta

from django.db.models import Avg, Count, DurationField, Exists, ExpressionWrapper, F, OuterRef, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from projects.models import Sprint
from tasks.models import Subtask, Task, TaskDependency

DONE = Task.Status.DONE
IN_PROGRESS = Task.Status.IN_PROGRESS
PENDING = Task.Status.PENDING

DEFAULT_PERIOD_DAYS = 90
MONTHLY_THRESHOLD_DAYS = 182
VELOCITY_SPRINT_LIMIT = 12

PACE_LABELS = {
    "ahead": "Adiantada",
    "on_track": "No ritmo",
    "behind": "Atrasada",
    "not_started": "Não iniciada",
    "empty": "Sem tarefas",
}


def organization_tasks(organization):
    return Task.objects.filter(project__organization=organization)


def apply_filters(queryset, project=None, sprint=None):
    if project is not None:
        queryset = queryset.filter(project=project)
    if sprint is not None:
        queryset = queryset.filter(sprint=sprint)
    return queryset


def resolve_period(start=None, end=None, today=None):
    today = today or timezone.localdate()
    end = end or today
    if start is None:
        start = end - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if end < start:
        end = start
    return start, end


def completed_between(start, end):
    return Q(status=DONE, completed_at__date__gte=start, completed_at__date__lte=end)


def overdue_condition(today):
    return Q(due_date__lt=today) & ~Q(status=DONE)


def blocked_condition():
    pending_dependency = TaskDependency.objects.filter(task=OuterRef("pk")).exclude(depends_on__status=DONE)
    open_subtask = Subtask.objects.filter(task=OuterRef("pk"), is_done=False)
    return ~Q(status=DONE) & (Q(Exists(pending_dependency)) | Q(Exists(open_subtask)))


def elapsed(end_field, start_field):
    return ExpressionWrapper(F(end_field) - F(start_field), output_field=DurationField())


def to_days(value):
    if value is None:
        return None
    return round(value.total_seconds() / 86400, 1)


def percent(part, whole):
    if not whole:
        return None
    return round(part * 100 / whole, 1)


def kpis(queryset, start, end, today=None):
    today = today or timezone.localdate()
    period = completed_between(start, end)
    with_due_date = period & Q(due_date__isnull=False)
    data = queryset.order_by().aggregate(
        total=Count("pk"),
        wip=Count("pk", filter=Q(status=IN_PROGRESS)),
        done=Count("pk", filter=Q(status=DONE)),
        overdue=Count("pk", filter=overdue_condition(today)),
        blocked=Count("pk", filter=blocked_condition()),
        throughput=Count("pk", filter=period),
        lead_time=Avg(elapsed("completed_at", "created_at"), filter=period),
        cycle_time=Avg(elapsed("completed_at", "started_at"), filter=period & Q(started_at__isnull=False)),
        due_completed=Count("pk", filter=with_due_date),
        on_time=Count("pk", filter=with_due_date & Q(completed_at__date__lte=F("due_date"))),
    )
    return {
        "total": data["total"],
        "wip": data["wip"],
        "done": data["done"],
        "overdue": data["overdue"],
        "blocked": data["blocked"],
        "completion_rate": percent(data["done"], data["total"]),
        "throughput": data["throughput"],
        "lead_time_days": to_days(data["lead_time"]),
        "cycle_time_days": to_days(data["cycle_time"]),
        "on_time_rate": percent(data["on_time"], data["due_completed"]),
        "on_time": data["on_time"],
        "due_completed": data["due_completed"],
    }


def status_distribution(queryset):
    counts = dict(queryset.order_by().values_list("status").annotate(total=Count("pk")))
    return [
        {"status": value, "label": label, "total": counts.get(value, 0)}
        for value, label in Task.Status.choices
    ]


def bucket_starts(start, end, monthly):
    if monthly:
        current = start.replace(day=1)
    else:
        current = start - timedelta(days=start.weekday())
    buckets = []
    while current <= end:
        buckets.append(current)
        if monthly:
            year, month = divmod(current.month, 12)
            current = date(current.year + year, month + 1, 1)
        else:
            current += timedelta(days=7)
    return buckets


def bucket_key(value):
    return value.date() if hasattr(value, "date") else value


def flow_series(queryset, start, end):
    monthly = (end - start).days >= MONTHLY_THRESHOLD_DAYS
    trunc = TruncMonth if monthly else TruncWeek
    queryset = queryset.order_by()
    created = (
        queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(bucket=trunc("created_at"))
        .values("bucket")
        .annotate(total=Count("pk"))
    )
    completed = (
        queryset.filter(completed_between(start, end))
        .annotate(bucket=trunc("completed_at"))
        .values("bucket")
        .annotate(total=Count("pk"))
    )
    created_by_bucket = {bucket_key(row["bucket"]): row["total"] for row in created}
    completed_by_bucket = {bucket_key(row["bucket"]): row["total"] for row in completed}
    buckets = bucket_starts(start, end, monthly)
    label_format = "%m/%Y" if monthly else "%d/%m"
    return {
        "granularity": "month" if monthly else "week",
        "labels": [bucket.strftime(label_format) for bucket in buckets],
        "periods": [bucket.isoformat() for bucket in buckets],
        "created": [created_by_bucket.get(bucket, 0) for bucket in buckets],
        "completed": [completed_by_bucket.get(bucket, 0) for bucket in buckets],
    }


def velocity(queryset, today=None):
    today = today or timezone.localdate()
    rows = list(
        queryset.filter(sprint__isnull=False, sprint__start_date__lte=today)
        .values("sprint_id", "sprint__name", "sprint__project__name", "sprint__start_date", "sprint__end_date")
        .annotate(
            committed=Count("pk"),
            completed=Count(
                "pk",
                filter=Q(
                    status=DONE,
                    completed_at__date__gte=F("sprint__start_date"),
                    completed_at__date__lte=F("sprint__end_date"),
                ),
            ),
        )
        .order_by("sprint__start_date", "sprint_id")
    )[-VELOCITY_SPRINT_LIMIT:]
    several_projects = len({row["sprint__project__name"] for row in rows}) > 1
    sprints = []
    for row in rows:
        finished = row["sprint__end_date"] < today
        name = row["sprint__name"]
        project = row["sprint__project__name"]
        sprints.append(
            {
                "id": row["sprint_id"],
                "name": name,
                "project": project,
                "label": f"{project} · {name}" if several_projects else name,
                "start_date": row["sprint__start_date"],
                "end_date": row["sprint__end_date"],
                "state": Sprint.State.FINISHED if finished else Sprint.State.ACTIVE,
                "committed": row["committed"],
                "completed": row["completed"],
            }
        )
    finished_values = [sprint["completed"] for sprint in sprints if sprint["state"] == Sprint.State.FINISHED]
    average = round(sum(finished_values) / len(finished_values), 1) if finished_values else None
    return {
        "labels": [sprint["label"] for sprint in sprints],
        "committed": [sprint["committed"] for sprint in sprints],
        "completed": [sprint["completed"] for sprint in sprints],
        "sprints": sprints,
        "average": average,
    }


def member_workload(queryset, start, end, today=None):
    today = today or timezone.localdate()
    rows = (
        queryset.values("assignee_id", "assignee__name")
        .annotate(
            open=Count("pk", filter=~Q(status=DONE)),
            in_progress=Count("pk", filter=Q(status=IN_PROGRESS)),
            done_in_period=Count("pk", filter=completed_between(start, end)),
            overdue=Count("pk", filter=overdue_condition(today)),
        )
        .order_by("-open", "-overdue", "-done_in_period", "assignee__name")
    )
    return [
        {
            "member_id": row["assignee_id"],
            "name": row["assignee__name"] or "Sem responsável",
            "open": row["open"],
            "in_progress": row["in_progress"],
            "done_in_period": row["done_in_period"],
            "overdue": row["overdue"],
        }
        for row in rows
        if row["open"] or row["done_in_period"]
    ]


def project_progress(queryset, today=None):
    today = today or timezone.localdate()
    rows = queryset.values("project_id", "project__name").annotate(
        total=Count("pk"),
        done=Count("pk", filter=Q(status=DONE)),
        wip=Count("pk", filter=Q(status=IN_PROGRESS)),
        overdue=Count("pk", filter=overdue_condition(today)),
    )
    projects = [
        {
            "project_id": row["project_id"],
            "name": row["project__name"],
            "total": row["total"],
            "done": row["done"],
            "wip": row["wip"],
            "overdue": row["overdue"],
            "progress": round(row["done"] * 100 / row["total"]) if row["total"] else 0,
        }
        for row in rows.order_by()
    ]
    return sorted(projects, key=lambda project: (-project["progress"], project["name"]))


def default_sprint(sprints, today=None):
    today = today or timezone.localdate()
    sprints = list(sprints)
    active = [sprint for sprint in sprints if sprint.start_date <= today <= sprint.end_date]
    if active:
        return min(active, key=lambda sprint: (sprint.end_date, sprint.pk))
    finished = [sprint for sprint in sprints if sprint.end_date < today]
    if finished:
        return max(finished, key=lambda sprint: (sprint.end_date, sprint.pk))
    planned = [sprint for sprint in sprints if sprint.start_date > today]
    if planned:
        return min(planned, key=lambda sprint: (sprint.start_date, sprint.pk))
    return None


def pace(remaining, ideal, tolerance):
    difference = remaining - ideal
    if difference < -tolerance:
        return "ahead"
    if difference > tolerance:
        return "behind"
    return "on_track"


def sprint_burndown(sprint, today=None, queryset=None):
    today = today or timezone.localdate()
    tasks = queryset if queryset is not None else Task.objects.all()
    rows = (
        tasks.filter(sprint=sprint)
        .order_by()
        .values(day=TruncDate("completed_at"))
        .annotate(total=Count("pk"))
    )
    completions = {row["day"]: row["total"] for row in rows}
    total = sum(completions.values())
    done_by_day = {day: count for day, count in completions.items() if day is not None}

    days = sprint.duration_days()
    dates = [sprint.start_date + timedelta(days=offset) for offset in range(days)]
    ideal = [round(total * (days - index) / days, 2) for index in range(days + 1)]

    cumulative = sum(count for day, count in done_by_day.items() if day < sprint.start_date)
    remaining = [total - cumulative if sprint.start_date <= today else None]
    for day in dates:
        cumulative += done_by_day.get(day, 0)
        remaining.append(total - cumulative if day <= today else None)
    completed = [None if value is None else total - value for value in remaining]

    last_index = max((index for index, value in enumerate(remaining) if value is not None), default=None)
    if total == 0:
        status = "empty"
    elif last_index is None:
        status = "not_started"
    else:
        status = pace(remaining[last_index], ideal[last_index], max(0.5, total / days))

    state = sprint.state(today)
    if state == Sprint.State.ACTIVE:
        days_remaining = (sprint.end_date - today).days
    elif state == Sprint.State.PLANNED:
        days_remaining = days
    else:
        days_remaining = 0

    completed_in_window = completed[last_index] if last_index is not None else 0
    completed_after_end = sum(count for day, count in done_by_day.items() if day > sprint.end_date)

    return {
        "sprint": {
            "id": sprint.pk,
            "name": sprint.name,
            "project": sprint.project.name,
            "start_date": sprint.start_date,
            "end_date": sprint.end_date,
            "state": state,
            "state_label": Sprint.State(state).label,
            "duration_days": days,
        },
        "labels": ["Início"] + [day.strftime("%d/%m") for day in dates],
        "dates": [None] + [day.isoformat() for day in dates],
        "ideal": ideal,
        "remaining": remaining,
        "ideal_completed": [round(total - value, 2) for value in ideal],
        "completed": completed,
        "scope": [total] * (days + 1),
        "total": total,
        "completed_count": completed_in_window,
        "remaining_count": total - completed_in_window,
        "completed_after_end": completed_after_end,
        "days_remaining": days_remaining,
        "status": status,
        "status_label": PACE_LABELS[status],
    }


def tasks_active_in_period(queryset, start, end):
    return queryset.filter(created_at__date__lte=end).filter(
        Q(completed_at__isnull=True) | Q(completed_at__date__gte=start)
    )


def task_report(queryset, start, end):
    return (
        tasks_active_in_period(queryset, start, end)
        .select_related("project", "sprint", "assignee")
        .annotate(
            lead_time=elapsed("completed_at", "created_at"),
            cycle_time=elapsed("completed_at", "started_at"),
        )
        .order_by("project__name", "created_at", "pk")
    )

import csv

from django.utils import timezone

from . import metrics

CSV_HEADER = [
    "Tarefa",
    "Projeto",
    "Sprint",
    "Responsável",
    "Status",
    "Criada em",
    "Iniciada em",
    "Concluída em",
    "Prazo",
    "Lead time (dias)",
    "Cycle time (dias)",
    "No prazo",
]
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def format_datetime(value):
    if value is None:
        return ""
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def format_days(value):
    days = metrics.to_days(value)
    if days is None:
        return ""
    return f"{days:.1f}".replace(".", ",")


def on_time_label(task):
    if task.completed_at is None or task.due_date is None:
        return ""
    return "Sim" if timezone.localtime(task.completed_at).date() <= task.due_date else "Não"


def task_row(task):
    return [
        task.title,
        task.project.name,
        task.sprint.name if task.sprint else "",
        task.assignee.name if task.assignee else "",
        task.get_status_display(),
        format_datetime(task.created_at),
        format_datetime(task.started_at),
        format_datetime(task.completed_at),
        task.due_date.strftime("%d/%m/%Y") if task.due_date else "",
        format_days(task.lead_time),
        format_days(task.cycle_time),
        on_time_label(task),
    ]


def write_tasks_csv(stream, tasks):
    stream.write("﻿")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(CSV_HEADER)
    for task in tasks:
        writer.writerow([safe_cell(value) for value in task_row(task)])

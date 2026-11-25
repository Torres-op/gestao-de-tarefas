import csv
import io
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import Organization, Profile
from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency

from . import metrics
from .exports import CSV_HEADER

PASSWORD = "senha-segura-123"


def moment(day, hour=9, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def make_user(username, organization=None, role=Profile.Role.OPERATOR):
    user = User.objects.create_user(username=username, password=PASSWORD)
    if organization:
        Profile.objects.create(user=user, organization=organization, role=role)
    return user


def make_task(project, title, status=Task.Status.PENDING, created=None, started=None, completed=None, **fields):
    task = Task.objects.create(
        project=project,
        title=title,
        status=status,
        started_at=started,
        completed_at=completed,
        **fields,
    )
    if created:
        Task.objects.filter(pk=task.pk).update(created_at=created)
        task.created_at = created
    return task


class DashboardDataMixin:
    def setUp(self):
        self.today = timezone.localdate()
        today = self.today

        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")
        self.admin_a = make_user("admin.a", self.org_a, Profile.Role.ADMIN)
        self.operator_a = make_user("operador.a", self.org_a)
        self.admin_b = make_user("admin.b", self.org_b, Profile.Role.ADMIN)

        self.project_a = Project.objects.create(organization=self.org_a, name="Projeto A")
        self.project_b = Project.objects.create(organization=self.org_b, name="Projeto B")
        self.member_a = Member.objects.create(organization=self.org_a, name="Ana", email="ana@a.com")

        self.sprint_a = Sprint.objects.create(
            project=self.project_a,
            name="Sprint A",
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=3),
        )

        self.done_on_time = make_task(
            self.project_a,
            "Concluída no prazo",
            Task.Status.DONE,
            created=moment(today - timedelta(days=10)),
            started=moment(today - timedelta(days=8)),
            completed=moment(today - timedelta(days=5)),
            due_date=today - timedelta(days=4),
            assignee=self.member_a,
        )
        self.done_late = make_task(
            self.project_a,
            "=SOMA(1+1)",
            Task.Status.DONE,
            created=moment(today - timedelta(days=6), 21),
            started=moment(today - timedelta(days=4), 21),
            completed=moment(today - timedelta(days=3), 21),
            due_date=today - timedelta(days=4),
            assignee=self.member_a,
            sprint=self.sprint_a,
        )
        self.doing = make_task(
            self.project_a,
            "Em andamento atrasada",
            Task.Status.IN_PROGRESS,
            created=moment(today - timedelta(days=2)),
            started=moment(today - timedelta(days=1)),
            due_date=today - timedelta(days=1),
            assignee=self.member_a,
            sprint=self.sprint_a,
        )
        Subtask.objects.create(task=self.doing, title="Aberta")

        for index in range(5):
            make_task(self.project_b, f"Tarefa B{index}", created=moment(today - timedelta(days=1)))

    def period(self, days_back=30):
        return self.today - timedelta(days=days_back), self.today


class KpiMetricsTests(DashboardDataMixin, TestCase):
    def test_totals_only_include_the_organization(self):
        start, end = self.period()
        data = metrics.kpis(metrics.organization_tasks(self.org_a), start, end, self.today)

        self.assertEqual(data["total"], 3)
        self.assertEqual(data["done"], 2)
        self.assertEqual(data["wip"], 1)
        self.assertEqual(data["overdue"], 1)
        self.assertEqual(data["blocked"], 1)
        self.assertEqual(data["completion_rate"], 66.7)
        self.assertEqual(metrics.kpis(metrics.organization_tasks(self.org_b), start, end, self.today)["total"], 5)

    def test_lead_time_cycle_time_and_on_time_rate(self):
        start, end = self.period()
        data = metrics.kpis(metrics.organization_tasks(self.org_a), start, end, self.today)

        self.assertEqual(data["throughput"], 2)
        self.assertEqual(data["lead_time_days"], 4.0)
        self.assertEqual(data["cycle_time_days"], 2.0)
        self.assertEqual(data["on_time"], 1)
        self.assertEqual(data["due_completed"], 2)
        self.assertEqual(data["on_time_rate"], 50.0)

    def test_period_filters_flow_metrics_but_not_snapshot(self):
        start, end = self.today - timedelta(days=4), self.today
        data = metrics.kpis(metrics.organization_tasks(self.org_a), start, end, self.today)

        self.assertEqual(data["throughput"], 1)
        self.assertEqual(data["lead_time_days"], 3.0)
        self.assertEqual(data["cycle_time_days"], 1.0)
        self.assertEqual(data["on_time_rate"], 0.0)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["done"], 2)

    def test_blocked_by_pending_dependency(self):
        waiting = make_task(self.project_a, "Esperando")
        TaskDependency.objects.create(task=waiting, depends_on=self.doing)
        start, end = self.period()

        data = metrics.kpis(metrics.organization_tasks(self.org_a), start, end, self.today)

        self.assertEqual(data["blocked"], 2)

    def test_status_distribution_and_flow_series(self):
        tasks = metrics.organization_tasks(self.org_a)
        distribution = {item["status"]: item["total"] for item in metrics.status_distribution(tasks)}
        self.assertEqual(distribution, {"pending": 0, "in_progress": 1, "done": 2})

        start, end = self.period(20)
        flow = metrics.flow_series(tasks, start, end)
        self.assertEqual(flow["granularity"], "week")
        self.assertEqual(sum(flow["completed"]), 2)
        self.assertEqual(sum(flow["created"]), 3)
        self.assertEqual(len(flow["labels"]), len(flow["created"]))

    def test_member_workload_and_project_progress(self):
        start, end = self.period()
        tasks = metrics.organization_tasks(self.org_a)

        workload = metrics.member_workload(tasks, start, end, self.today)
        self.assertEqual(len(workload), 1)
        self.assertEqual(
            workload[0],
            {"member_id": self.member_a.pk, "name": "Ana", "open": 1, "in_progress": 1, "done_in_period": 2, "overdue": 1},
        )
        projects = metrics.project_progress(tasks, self.today)
        self.assertEqual(projects[0]["progress"], 67)
        self.assertEqual(projects[0]["total"], 3)


class SprintBurndownTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Org Sprint")
        self.project = Project.objects.create(organization=self.organization, name="Projeto Sprint")
        self.sprint = Sprint.objects.create(
            project=self.project,
            name="Sprint 5 dias",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 6),
        )
        done = Task.Status.DONE
        make_task(self.project, "Dia 1", done, completed=moment(date(2026, 3, 2), 15), sprint=self.sprint)
        make_task(self.project, "Dia 3 manhã", done, completed=moment(date(2026, 3, 4), 10), sprint=self.sprint)
        make_task(self.project, "Dia 3 noite", done, completed=moment(date(2026, 3, 4), 23, 30), sprint=self.sprint)
        make_task(self.project, "Depois do fim", done, completed=moment(date(2026, 3, 8), 11), sprint=self.sprint)
        make_task(self.project, "Aberta", sprint=self.sprint)
        make_task(self.project, "Fora da sprint", done, completed=moment(date(2026, 3, 3), 11))

    def test_ideal_and_real_lines_with_future_days(self):
        data = metrics.sprint_burndown(self.sprint, today=date(2026, 3, 4))

        self.assertEqual(data["labels"], ["Início", "02/03", "03/03", "04/03", "05/03", "06/03"])
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["ideal"], [5, 4, 3, 2, 1, 0])
        self.assertEqual(data["remaining"], [5, 4, 4, 2, None, None])
        self.assertEqual(data["completed"], [0, 1, 1, 3, None, None])
        self.assertEqual(data["ideal_completed"], [0, 1, 2, 3, 4, 5])
        self.assertEqual(data["scope"], [5] * 6)
        self.assertEqual(data["status"], "on_track")
        self.assertEqual(data["days_remaining"], 2)
        self.assertEqual(data["sprint"]["state"], Sprint.State.ACTIVE)

    def test_completion_after_end_does_not_reduce_window(self):
        data = metrics.sprint_burndown(self.sprint, today=date(2026, 3, 10))

        self.assertEqual(data["remaining"], [5, 4, 4, 2, 2, 2])
        self.assertEqual(data["completed_count"], 3)
        self.assertEqual(data["completed_after_end"], 1)
        self.assertEqual(data["status"], "behind")
        self.assertEqual(data["days_remaining"], 0)

    def test_planned_sprint_has_no_real_points(self):
        data = metrics.sprint_burndown(self.sprint, today=date(2026, 3, 1))

        self.assertEqual(data["remaining"], [None] * 6)
        self.assertEqual(data["status"], "not_started")
        self.assertEqual(data["days_remaining"], 5)

    def test_velocity_counts_only_completions_inside_the_window(self):
        tasks = metrics.organization_tasks(self.organization)
        data = metrics.velocity(tasks, today=date(2026, 3, 10))

        self.assertEqual(data["labels"], ["Sprint 5 dias"])
        self.assertEqual(data["committed"], [5])
        self.assertEqual(data["completed"], [3])
        self.assertEqual(data["average"], 3.0)

    def test_default_sprint_selection(self):
        today = date(2026, 6, 15)
        finished_old = Sprint(pk=1, start_date=date(2026, 5, 1), end_date=date(2026, 5, 10))
        finished_recent = Sprint(pk=2, start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        active_late = Sprint(pk=3, start_date=date(2026, 6, 10), end_date=date(2026, 6, 25))
        active_soon = Sprint(pk=4, start_date=date(2026, 6, 14), end_date=date(2026, 6, 20))
        planned_far = Sprint(pk=5, start_date=date(2026, 8, 1), end_date=date(2026, 8, 10))
        planned_near = Sprint(pk=6, start_date=date(2026, 7, 1), end_date=date(2026, 7, 10))

        everything = [finished_old, finished_recent, active_late, active_soon, planned_far, planned_near]
        self.assertEqual(metrics.default_sprint(everything, today), active_soon)
        self.assertEqual(metrics.default_sprint([finished_old, finished_recent, planned_near], today), finished_recent)
        self.assertEqual(metrics.default_sprint([planned_far, planned_near], today), planned_near)
        self.assertIsNone(metrics.default_sprint([], today))


class DashboardViewTests(DashboardDataMixin, TestCase):
    url = reverse("dashboard:index")

    def test_admin_sees_all_blocks(self):
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["kpis"]["total"], 3)
        self.assertTrue(response.context["show_admin_blocks"])
        self.assertIsNotNone(response.context["flow"])
        self.assertEqual(response.context["burndown"]["sprint"]["id"], self.sprint_a.pk)
        self.assertContains(response, 'id="flow-data"')
        self.assertContains(response, reverse("dashboard:export_csv"))

    def test_operator_does_not_receive_admin_blocks(self):
        self.client.login(username="operador.a", password=PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_admin_blocks"])
        self.assertIsNone(response.context["flow"])
        self.assertIsNone(response.context["velocity"])
        self.assertNotContains(response, 'id="flow-data"')
        self.assertNotContains(response, reverse("dashboard:export_csv"))
        self.assertContains(response, 'id="burndown-data"')

    def test_period_filter_from_querystring(self):
        self.client.login(username="admin.a", password=PASSWORD)
        start = (self.today - timedelta(days=4)).isoformat()
        response = self.client.get(self.url, {"start": start, "end": self.today.isoformat()})

        self.assertEqual(response.context["kpis"]["throughput"], 1)
        self.assertFalse(response.context["filters"].default_period)

    def test_invalid_filters_are_ignored_without_server_error(self):
        self.client.login(username="admin.a", password=PASSWORD)
        cases = [
            {"start": "abc", "end": "2026-13-45", "project": "x", "sprint": "999999"},
            {"start": "2026-05-10", "end": "2026-05-01"},
            {"start": "0001-01-01", "end": "9999-12-31"},
            {"project": str(self.project_b.pk)},
        ]
        for params in cases:
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(response.context["kpis"]["total"], 3)

    def test_sprint_of_other_project_is_rejected(self):
        other_project = Project.objects.create(organization=self.org_a, name="Outro")
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.url, {"project": other_project.pk, "sprint": self.sprint_a.pk})

        self.assertIn("sprint", response.context["form"].errors)

    def test_sprint_filter_scopes_metrics(self):
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.url, {"sprint": self.sprint_a.pk})

        self.assertEqual(response.context["kpis"]["total"], 2)
        self.assertEqual(response.context["burndown"]["total"], 2)

    def test_empty_organization_renders_without_errors(self):
        empty = Organization.objects.create(name="Vazia")
        make_user("admin.vazia", empty, Profile.Role.ADMIN)
        self.client.login(username="admin.vazia", password=PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["kpis"]["total"], 0)
        self.assertIsNone(response.context["kpis"]["completion_rate"])
        self.assertIsNone(response.context["burndown"])
        self.assertContains(response, "Nenhuma sprint cadastrada")

    def test_query_count_does_not_grow_with_tasks(self):
        self.client.login(username="admin.a", password=PASSWORD)
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as initial:
            self.client.get(self.url)

        for index in range(15):
            member = Member.objects.create(organization=self.org_a, name=f"Membro {index}", email=f"m{index}@a.com")
            task = make_task(self.project_a, f"Extra {index}", assignee=member, sprint=self.sprint_a)
            Subtask.objects.create(task=task, title="Sub")
            TaskDependency.objects.create(task=task, depends_on=self.doing)
        Project.objects.create(organization=self.org_a, name="Projeto extra")

        with CaptureQueriesContext(connection) as grown:
            response = self.client.get(self.url)

        self.assertEqual(response.context["kpis"]["total"], 18)
        self.assertEqual(len(grown.captured_queries), len(initial.captured_queries))
        self.assertLessEqual(len(grown.captured_queries), 20)


class ExportCsvTests(DashboardDataMixin, TestCase):
    url = reverse("dashboard:export_csv")

    def read_rows(self, response):
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        return list(csv.reader(io.StringIO(content.lstrip("﻿")), delimiter=";"))

    def test_operator_cannot_export(self):
        self.client.login(username="operador.a", password=PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_admin_exports_organization_tasks(self):
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(f"grello-tarefas-{self.today:%Y-%m-%d}.csv", response["Content-Disposition"])
        rows = self.read_rows(response)
        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows), 4)
        titles = [row[0] for row in rows[1:]]
        self.assertIn("'=SOMA(1+1)", titles)
        self.assertNotIn("=SOMA(1+1)", titles)
        self.assertFalse(any(title.startswith("Tarefa B") for title in titles))

        late = next(row for row in rows if row[0] == "'=SOMA(1+1)")
        self.assertEqual(late[2], "Sprint A")
        self.assertEqual(late[4], "Concluída")
        self.assertEqual(late[9], "3,0")
        self.assertEqual(late[10], "1,0")
        self.assertEqual(late[11], "Não")
        on_time = next(row for row in rows if row[0] == "Concluída no prazo")
        self.assertEqual(on_time[11], "Sim")

    def test_export_respects_filters(self):
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.url, {"sprint": self.sprint_a.pk})
        self.assertEqual(len(self.read_rows(response)), 3)

        start = (self.today - timedelta(days=2)).isoformat()
        response = self.client.get(self.url, {"start": start, "end": self.today.isoformat()})
        self.assertEqual([row[0] for row in self.read_rows(response)[1:]], ["Em andamento atrasada"])

    def test_export_has_no_n_plus_one(self):
        self.client.login(username="admin.a", password=PASSWORD)
        with CaptureQueriesContext(connection) as initial:
            self.client.get(self.url)
        for index in range(10):
            make_task(self.project_a, f"Extra {index}", assignee=self.member_a, sprint=self.sprint_a)
        with CaptureQueriesContext(connection) as grown:
            self.client.get(self.url)

        self.assertEqual(len(grown.captured_queries), len(initial.captured_queries))


class DashboardApiTests(DashboardDataMixin, TestCase):
    summary_url = reverse("dashboard_api:summary")
    burndown_url = reverse("dashboard_api:burndown")

    def test_summary_is_isolated_by_organization(self):
        self.client.login(username="admin.b", password=PASSWORD)
        response = self.client.get(self.summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kpis"]["total"], 5)
        self.assertIsNone(response.json()["burndown"])

    def test_operator_summary_omits_admin_blocks(self):
        self.client.login(username="operador.a", password=PASSWORD)
        data = self.client.get(self.summary_url).json()

        self.assertEqual(data["kpis"]["total"], 3)
        self.assertNotIn("flow", data)
        self.assertNotIn("velocity", data)

        self.client.login(username="admin.a", password=PASSWORD)
        data = self.client.get(self.summary_url).json()
        self.assertIn("flow", data)
        self.assertIn("velocity", data)

    def test_summary_rejects_invalid_filters(self):
        self.client.login(username="admin.a", password=PASSWORD)
        response = self.client.get(self.summary_url, {"start": "2026-05-10", "end": "2026-05-01"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("end", response.json()["errors"])

    def test_burndown_of_other_organization_is_not_found(self):
        self.client.login(username="admin.b", password=PASSWORD)

        self.assertEqual(self.client.get(self.burndown_url, {"sprint": self.sprint_a.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.burndown_url).status_code, 404)
        self.assertEqual(self.client.get(self.burndown_url, {"sprint": "abc"}).status_code, 400)

    def test_burndown_of_own_sprint(self):
        self.client.login(username="operador.a", password=PASSWORD)
        response = self.client.get(self.burndown_url, {"sprint": self.sprint_a.pk})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["sprint"]["id"], self.sprint_a.pk)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["labels"]), self.sprint_a.duration_days() + 1)

    def test_user_without_profile_is_forbidden(self):
        make_user("sem.perfil")
        self.client.login(username="sem.perfil", password=PASSWORD)

        self.assertEqual(self.client.get(self.summary_url).status_code, 403)
        self.assertEqual(self.client.get(self.burndown_url).status_code, 403)

    def test_anonymous_is_forbidden(self):
        self.assertEqual(self.client.get(self.summary_url).status_code, 403)

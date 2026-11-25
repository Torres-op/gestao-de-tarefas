from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Organization, Profile
from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency

User = get_user_model()


class ApiTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Labs")
        cls.other_org = Organization.objects.create(name="Acme")
        cls.admin = cls.create_user("admin", cls.org, Profile.Role.ADMIN)
        cls.operator = cls.create_user("operador", cls.org, Profile.Role.OPERATOR)
        cls.other_admin = cls.create_user("admin.acme", cls.other_org, Profile.Role.ADMIN)
        cls.project = Project.objects.create(organization=cls.org, name="Portal")
        cls.sprint = Sprint.objects.create(
            project=cls.project, name="Sprint 1", start_date=date(2026, 1, 1), end_date=date(2026, 1, 14)
        )
        cls.member = Member.objects.create(organization=cls.org, name="Ana", email="ana@labs.com")
        cls.task = Task.objects.create(project=cls.project, title="Modelar banco", assignee=cls.member)
        cls.other_project = Project.objects.create(organization=cls.other_org, name="Loja")
        cls.other_member = Member.objects.create(organization=cls.other_org, name="Bia", email="bia@acme.com")
        cls.other_task = Task.objects.create(project=cls.other_project, title="Checkout")

    @staticmethod
    def create_user(username, organization, role):
        user = User.objects.create_user(username=username, password="senha-forte-123")
        Profile.objects.create(user=user, organization=organization, role=role)
        return user

    def detail(self, resource, pk):
        return f"/api/{resource}/{pk}/"


class AuthenticationTests(ApiTestCase):
    def test_anonymous_receives_403_json(self):
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_anonymous_root_receives_403(self):
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_session_login_reaches_api_and_browsable_api(self):
        self.client.login(username="operador", password="senha-forte-123")
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get("/api/tasks/", HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Modelar banco")
        self.assertNotContains(response, "Checkout")

    def test_user_without_profile_receives_403(self):
        user = User.objects.create_user(username="sem.perfil", password="senha-forte-123")
        self.client.force_authenticate(user)
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("organização", response.json()["detail"])


class OrganizationIsolationTests(ApiTestCase):
    def setUp(self):
        self.client.force_authenticate(self.operator)

    def test_lists_only_own_organization(self):
        cases = {
            "projects": self.project.pk,
            "members": self.member.pk,
            "tasks": self.task.pk,
            "sprints": self.sprint.pk,
        }
        for resource, expected_pk in cases.items():
            with self.subTest(resource=resource):
                response = self.client.get(f"/api/{resource}/")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual([item["id"] for item in response.json()], [expected_pk])

    def test_retrieve_from_other_organization_returns_404(self):
        cases = {
            "projects": self.other_project.pk,
            "members": self.other_member.pk,
            "tasks": self.other_task.pk,
        }
        for resource, pk in cases.items():
            with self.subTest(resource=resource):
                response = self.client.get(self.detail(resource, pk))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_task_with_other_organization_project_returns_400(self):
        response = self.client.post("/api/tasks/", {"project": self.other_project.pk, "title": "Invasão"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project", response.json())
        self.assertFalse(Task.objects.filter(title="Invasão").exists())

    def test_create_task_with_other_organization_assignee_returns_400(self):
        response = self.client.post(
            "/api/tasks/", {"project": self.project.pk, "title": "Invasão", "assignee": self.other_member.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assignee", response.json())

    def test_organization_in_payload_is_ignored(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/projects/", {"name": "Novo", "organization": self.other_org.pk})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.get(pk=response.json()["id"]).organization, self.org)

    def test_task_list_filters(self):
        Task.objects.create(project=self.project, title="Outra", status=Task.Status.DONE, sprint=self.sprint)
        response = self.client.get("/api/tasks/", {"status": "done"})
        self.assertEqual([item["title"] for item in response.json()], ["Outra"])
        response = self.client.get("/api/tasks/", {"sprint": self.sprint.pk})
        self.assertEqual([item["title"] for item in response.json()], ["Outra"])
        response = self.client.get("/api/tasks/", {"assignee": self.member.pk})
        self.assertEqual([item["id"] for item in response.json()], [self.task.pk])


class RolePermissionTests(ApiTestCase):
    def test_operator_cannot_write_projects_sprints_or_members(self):
        self.client.force_authenticate(self.operator)
        cases = [
            ("post", "/api/projects/", {"name": "Novo"}),
            ("patch", self.detail("projects", self.project.pk), {"name": "X"}),
            ("delete", self.detail("projects", self.project.pk), None),
            (
                "post",
                "/api/sprints/",
                {"project": self.project.pk, "name": "S2", "start_date": "2026-02-01", "end_date": "2026-02-14"},
            ),
            ("patch", self.detail("sprints", self.sprint.pk), {"name": "X"}),
            ("delete", self.detail("sprints", self.sprint.pk), None),
            ("post", "/api/members/", {"name": "Caio", "email": "caio@labs.com"}),
            ("patch", self.detail("members", self.member.pk), {"name": "X"}),
            ("delete", self.detail("members", self.member.pk), None),
            ("delete", self.detail("tasks", self.task.pk), None),
        ]
        for method, url, data in cases:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Portal")

    def test_operator_can_create_and_edit_tasks_and_subtasks(self):
        self.client.force_authenticate(self.operator)
        response = self.client.post(
            "/api/tasks/", {"project": self.project.pk, "sprint": self.sprint.pk, "title": "Nova"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task_id = response.json()["id"]
        response = self.client.patch(self.detail("tasks", task_id), {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.json()["started_at"])
        response = self.client.post("/api/subtasks/", {"task": task_id, "title": "Passo 1"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        subtask_id = response.json()["id"]
        response = self.client.patch(self.detail("subtasks", subtask_id), {"title": "Passo 1 revisado"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(f"/api/subtasks/{subtask_id}/toggle/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["is_done"])
        response = self.client.delete(self.detail("subtasks", subtask_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_can_do_everything(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/projects/", {"name": "Novo", "start_date": "2026-03-01"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project_id = response.json()["id"]
        response = self.client.post(
            "/api/sprints/",
            {"project": project_id, "name": "S1", "start_date": "2026-03-01", "end_date": "2026-03-14"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sprint_id = response.json()["id"]
        response = self.client.post("/api/members/", {"name": "Caio", "email": "caio@labs.com"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        member_id = response.json()["id"]
        self.assertEqual(Member.objects.get(pk=member_id).organization, self.org)
        response = self.client.patch(self.detail("projects", project_id), {"name": "Renomeado"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for resource, pk in [
            ("tasks", self.task.pk),
            ("sprints", sprint_id),
            ("members", member_id),
            ("projects", project_id),
        ]:
            with self.subTest(resource=resource):
                response = self.client.delete(self.detail(resource, pk))
                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_model_clean_runs_on_project_and_sprint(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/projects/", {"name": "Datas", "start_date": "2026-03-10", "due_date": "2026-03-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("due_date", response.json())
        response = self.client.post(
            "/api/sprints/",
            {"project": self.project.pk, "name": "Sprint 1", "start_date": "2026-03-01", "end_date": "2026-03-14"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())


class TaskRulesTests(ApiTestCase):
    def setUp(self):
        self.client.force_authenticate(self.operator)
        self.prerequisite = Task.objects.create(project=self.project, title="Levantar requisitos")
        TaskDependency.objects.create(task=self.task, depends_on=self.prerequisite)

    def test_complete_blocked_returns_400_with_reason(self):
        response = self.client.post(f"/api/tasks/{self.task.pk}/complete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Levantar requisitos", response.json()["detail"])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.PENDING)

    def test_complete_allowed_returns_200_and_done(self):
        response = self.client.post(f"/api/tasks/{self.prerequisite.pk}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "done")
        response = self.client.post(f"/api/tasks/{self.task.pk}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "done")
        self.assertIsNotNone(response.json()["completed_at"])

    def test_reopen_blocked_by_completed_dependent(self):
        self.prerequisite.complete()
        self.task.complete()
        response = self.client.post(f"/api/tasks/{self.prerequisite.pk}/reopen/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Modelar banco", response.json()["detail"])
        response = self.client.post(f"/api/tasks/{self.task.pk}/reopen/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "in_progress")

    def test_patch_status_done_blocked_returns_400(self):
        response = self.client.patch(self.detail("tasks", self.task.pk), {"status": "done"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.json())
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.PENDING)

    def test_open_subtask_blocks_completion(self):
        self.prerequisite.complete()
        Subtask.objects.create(task=self.task, title="Revisar diagrama")
        response = self.client.post(f"/api/tasks/{self.task.pk}/complete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Revisar diagrama", response.json()["detail"])

    def test_task_exposes_blocking_information(self):
        response = self.client.get(self.detail("tasks", self.task.pk))
        data = response.json()
        self.assertTrue(data["is_blocked"])
        self.assertIn("Levantar requisitos", data["blocking_reason"])
        self.assertEqual(data["assignee_name"], "Ana")

    def test_dependency_creating_cycle_returns_400(self):
        response = self.client.post(
            "/api/dependencies/", {"task": self.prerequisite.pk, "depends_on": self.task.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ciclo", response.json()["depends_on"][0])

    def test_dependency_with_other_organization_task_returns_400(self):
        response = self.client.post(
            "/api/dependencies/", {"task": self.task.pk, "depends_on": self.other_task.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("depends_on", response.json())

    def test_sprint_from_other_project_returns_400(self):
        other = Project.objects.create(organization=self.org, name="Interno")
        loose = Task.objects.create(project=self.task.project, title="Avulsa")
        response = self.client.patch(self.detail("tasks", loose.pk), {"project": other.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(self.detail("tasks", loose.pk), {"sprint": self.sprint.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sprint", response.json())


class MemberEmailTests(ApiTestCase):
    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_duplicated_email_in_same_organization_returns_400(self):
        response = self.client.post("/api/members/", {"name": "Outra Ana", "email": "ANA@labs.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("e-mail", response.json()["email"][0])

    def test_same_email_allowed_in_other_organization(self):
        self.client.force_authenticate(self.other_admin)
        response = self.client.post("/api/members/", {"name": "Ana Acme", "email": "ana@labs.com"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_member_can_keep_own_email_on_update(self):
        response = self.client.put(
            self.detail("members", self.member.pk),
            {"name": "Ana Souza", "email": "ana@labs.com", "role": "", "is_active": True},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class QueryCountTests(ApiTestCase):
    def create_tasks(self, amount):
        for index in range(amount):
            task = Task.objects.create(
                project=self.project, sprint=self.sprint, assignee=self.member, title=f"Tarefa {index}"
            )
            Subtask.objects.create(task=task, title="Subtarefa")
            TaskDependency.objects.create(task=task, depends_on=self.task)

    def count_list_queries(self, url):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return len(context.captured_queries), len(response.json())

    def test_task_list_has_no_n_plus_one(self):
        self.client.force_authenticate(self.operator)
        self.create_tasks(2)
        baseline, size = self.count_list_queries("/api/tasks/")
        self.assertEqual(size, 3)
        self.create_tasks(10)
        queries, size = self.count_list_queries("/api/tasks/")
        self.assertEqual(size, 13)
        self.assertEqual(queries, baseline)
        self.assertLessEqual(queries, 8)

    def test_sprint_and_project_lists_have_no_n_plus_one(self):
        self.client.force_authenticate(self.operator)
        for url in ("/api/sprints/", "/api/projects/"):
            with self.subTest(url=url):
                baseline, _ = self.count_list_queries(url)
                self.create_tasks(5)
                queries, _ = self.count_list_queries(url)
                self.assertEqual(queries, baseline)

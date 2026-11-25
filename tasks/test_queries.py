from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.testing import QueryCountScenario


class TaskQueryCountTests(QueryCountScenario, TestCase):
    def test_filtered_task_list(self):
        url = f"{reverse('tasks:list')}?project={self.project.pk}&sprint={self.sprint.pk}&status=in_progress"
        self.assertQueriesStayAt(8, url)

    def test_task_list_as_operator(self):
        self.assertQueriesStayAt(8, reverse("tasks:list"), user=self.operator)

    def test_task_detail_with_dependencies_dependents_and_subtasks(self):
        self.assertQueriesStayAt(7, reverse("tasks:detail", args=[self.root.pk]))

    def test_task_create_form(self):
        self.assertQueriesStayAt(6, reverse("tasks:create"))

    def test_task_update_form(self):
        self.assertQueriesStayAt(7, reverse("tasks:update", args=[self.root.pk]))

    def test_task_delete_confirmation(self):
        self.assertQueriesStayAt(4, reverse("tasks:delete", args=[self.root.pk]))

    def test_dependency_form(self):
        self.assertQueriesStayAt(6, reverse("tasks:dependency_create", args=[self.root.pk]))

    def test_subtask_forms(self):
        urls = [
            reverse("tasks:subtask_create", args=[self.root.pk]),
            reverse("tasks:subtask_update", args=[self.subtask.pk]),
            reverse("tasks:subtask_delete", args=[self.subtask.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertQueriesStayAt(4, url)


class TaskAdminQueryCountTests(QueryCountScenario, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser = User.objects.create_superuser("root.consultas", "root@exemplo.com", "senha-root-123")

    def assertAdminQueriesStayAt(self, expected, url):
        self.client.force_login(self.superuser)
        self.get_ok(url)
        self.assertQueriesStayAt(expected, url, user=self.superuser)

    def test_task_changelist_selects_sprint_project(self):
        self.assertAdminQueriesStayAt(8, reverse("admin:tasks_task_changelist"))

    def test_task_change_form_sprint_choices(self):
        self.assertAdminQueriesStayAt(11, reverse("admin:tasks_task_change", args=[self.root.pk]))

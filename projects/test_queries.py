from django.test import TestCase
from django.urls import reverse

from core.testing import QueryCountScenario


class ProjectQueryCountTests(QueryCountScenario, TestCase):
    def test_project_list(self):
        self.assertQueriesStayAt(6, reverse("projects:list"))

    def test_project_list_second_page(self):
        self.assertQueriesStayAt(6, f"{reverse('projects:list')}?page=2")

    def test_project_detail(self):
        self.assertQueriesStayAt(9, reverse("projects:detail", args=[self.project.pk]))

    def test_project_create_form(self):
        self.assertQueriesStayAt(3, reverse("projects:create"))

    def test_project_update_form(self):
        self.assertQueriesStayAt(4, reverse("projects:update", args=[self.project.pk]))

    def test_project_delete_confirmation(self):
        self.assertQueriesStayAt(4, reverse("projects:delete", args=[self.project.pk]))

    def test_project_detail_as_operator(self):
        self.assertQueriesStayAt(9, reverse("projects:detail", args=[self.project.pk]), user=self.operator)


class SprintQueryCountTests(QueryCountScenario, TestCase):
    def test_sprint_detail(self):
        self.assertQueriesStayAt(7, reverse("projects:sprint_detail", args=[self.sprint.pk]))

    def test_sprint_create_form(self):
        self.assertQueriesStayAt(4, reverse("projects:sprint_create", args=[self.project.pk]))

    def test_sprint_update_form(self):
        self.assertQueriesStayAt(4, reverse("projects:sprint_update", args=[self.sprint.pk]))

    def test_sprint_delete_confirmation(self):
        self.assertQueriesStayAt(4, reverse("projects:sprint_delete", args=[self.sprint.pk]))

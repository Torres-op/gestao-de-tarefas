from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.testing import make_dependency, make_operator, make_organization, make_project, make_task

from .models import Task


def edit_payload(task, **changes):
    data = {
        "project": task.project_id,
        "sprint": "",
        "title": task.title,
        "description": task.description,
        "assignee": "",
        "status": task.status,
        "due_date": "",
    }
    data.update(changes)
    return data


class TaskProjectChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org A")
        cls.operator = make_operator("operador", cls.organization)
        cls.project = make_project(cls.organization, "Projeto 1")
        cls.other_project = make_project(cls.organization, "Projeto 2")
        cls.prerequisite = make_task(cls.project, "Pré-requisito")
        cls.dependent = make_task(cls.project, "Dependente")
        make_dependency(cls.dependent, cls.prerequisite)
        cls.loose = make_task(cls.project, "Avulsa")

    def setUp(self):
        self.client.force_login(self.operator)

    def assert_cannot_move(self, task):
        task = Task.objects.get(pk=task.pk)
        task.project = self.other_project
        with self.assertRaises(ValidationError) as context:
            task.full_clean()
        self.assertIn("project", context.exception.message_dict)

    def test_task_with_prerequisites_cannot_change_project(self):
        self.assert_cannot_move(self.dependent)

    def test_task_that_others_depend_on_cannot_change_project(self):
        self.assert_cannot_move(self.prerequisite)

    def test_html_form_refuses_moving_a_task_with_dependencies(self):
        response = self.client.post(
            reverse("tasks:update", args=[self.dependent.pk]),
            edit_payload(self.dependent, project=self.other_project.pk),
        )
        self.assertEqual(response.status_code, 200)
        self.dependent.refresh_from_db()
        self.assertEqual(self.dependent.project, self.project)

    def test_api_refuses_moving_a_task_with_dependencies(self):
        response = self.client.patch(
            f"/api/tasks/{self.prerequisite.pk}/",
            {"project": self.other_project.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("project", response.json())
        self.prerequisite.refresh_from_db()
        self.assertEqual(self.prerequisite.project, self.project)

    def test_task_without_dependencies_can_change_project(self):
        response = self.client.post(
            reverse("tasks:update", args=[self.loose.pk]),
            edit_payload(self.loose, project=self.other_project.pk),
        )
        self.assertEqual(response.status_code, 302)
        self.loose.refresh_from_db()
        self.assertEqual(self.loose.project, self.other_project)

    def test_editing_other_fields_of_a_task_with_dependencies_still_works(self):
        response = self.client.post(
            reverse("tasks:update", args=[self.dependent.pk]),
            edit_payload(self.dependent, title="Dependente renomeada"),
        )
        self.assertEqual(response.status_code, 302)
        self.dependent.refresh_from_db()
        self.assertEqual(self.dependent.title, "Dependente renomeada")

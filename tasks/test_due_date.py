from datetime import datetime, time

from django.test import TestCase
from django.utils import timezone

from core.testing import make_organization, make_project
from projects.models import Project

from .forms import TaskForm

ERROR = "O prazo não pode ser anterior a criação do projeto"


class TaskDueDateRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org A")
        cls.project = make_project(cls.organization)
        created_at = timezone.make_aware(datetime(2026, 3, 10, 23, 30))
        Project.objects.filter(pk=cls.project.pk).update(created_at=created_at)
        cls.project.refresh_from_db()

    def form(self, due_date):
        data = {"project": self.project.pk, "title": "Tarefa", "status": "pending", "due_date": due_date}
        return TaskForm(data=data, organization=self.organization)

    def test_due_date_before_project_creation_is_refused(self):
        form = self.form("2026-03-09")
        self.assertFalse(form.is_valid())
        self.assertIn(ERROR, form.non_field_errors())

    def test_due_date_on_the_local_creation_day_is_accepted(self):
        self.assertEqual(self.project.created_at.astimezone(timezone.get_current_timezone()).time(), time(23, 30))
        self.assertTrue(self.form("2026-03-10").is_valid())

    def test_due_date_after_project_creation_is_accepted(self):
        self.assertTrue(self.form("2026-04-01").is_valid())

    def test_task_without_due_date_is_accepted(self):
        self.assertTrue(self.form("").is_valid())

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.testing import make_admin, make_organization, make_project, make_sprint, make_task

from .models import MAX_SPRINT_DAYS, Sprint

START = date(2026, 3, 2)


class SprintDurationLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org A")
        cls.admin = make_admin("admin", cls.organization)
        cls.project = make_project(cls.organization)

    def test_sprint_with_the_maximum_duration_is_valid(self):
        sprint = Sprint(
            project=self.project, name="Longa", start_date=START, end_date=START + timedelta(days=MAX_SPRINT_DAYS - 1)
        )
        sprint.full_clean()

    def test_sprint_longer_than_the_maximum_is_refused_by_clean(self):
        sprint = Sprint(
            project=self.project, name="Longa", start_date=START, end_date=START + timedelta(days=MAX_SPRINT_DAYS)
        )
        with self.assertRaises(ValidationError) as context:
            sprint.full_clean()
        self.assertIn("end_date", context.exception.message_dict)

    def test_database_refuses_a_sprint_longer_than_the_maximum(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sprint.objects.create(
                project=self.project, name="Longa", start_date=START, end_date=START + timedelta(days=MAX_SPRINT_DAYS)
            )

    def test_html_form_refuses_a_centuries_long_sprint(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("projects:sprint_create", args=[self.project.pk]),
            {"name": "Eterna", "goal": "", "start_date": "0001-01-01", "end_date": "9999-12-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sprint.objects.filter(name="Eterna").exists())

    def test_api_refuses_a_centuries_long_sprint(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/api/sprints/",
            {"project": self.project.pk, "name": "Eterna", "start_date": "1900-01-01", "end_date": "2199-12-31"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.json())
        self.assertFalse(Sprint.objects.filter(name="Eterna").exists())


class SprintProjectChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org A")
        cls.admin = make_admin("admin", cls.organization)
        cls.project = make_project(cls.organization, "Projeto 1")
        cls.other_project = make_project(cls.organization, "Projeto 2")

    def test_sprint_with_tasks_cannot_change_project(self):
        sprint = make_sprint(self.project)
        make_task(self.project, sprint=sprint)
        sprint = Sprint.objects.get(pk=sprint.pk)
        sprint.project = self.other_project
        with self.assertRaises(ValidationError) as context:
            sprint.full_clean()
        self.assertIn("project", context.exception.message_dict)

    def test_api_refuses_moving_a_sprint_with_tasks(self):
        sprint = make_sprint(self.project)
        task = make_task(self.project, sprint=sprint)
        self.client.force_login(self.admin)
        response = self.client.patch(
            f"/api/sprints/{sprint.pk}/", {"project": self.other_project.pk}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("project", response.json())
        sprint.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(sprint.project, self.project)
        self.assertEqual(task.sprint.project, task.project)

    def test_empty_sprint_can_change_project(self):
        sprint = make_sprint(self.project)
        self.client.force_login(self.admin)
        response = self.client.patch(
            f"/api/sprints/{sprint.pk}/", {"project": self.other_project.pk}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        sprint.refresh_from_db()
        self.assertEqual(sprint.project, self.other_project)

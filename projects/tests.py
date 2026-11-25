from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.testing import (
    make_admin,
    make_operator,
    make_organization,
    make_project,
    make_sprint,
    make_task,
)
from tasks.models import Task

from .forms import SprintForm
from .models import Project, Sprint

START = date(2026, 3, 2)
END = date(2026, 3, 15)


class ProjectsFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Organização A")
        cls.admin = make_admin("admin.a", cls.organization)
        cls.operator = make_operator("operador.a", cls.organization)
        cls.project = make_project(cls.organization, "Projeto A")
        cls.sprint = make_sprint(cls.project, "Sprint 1", start=START, end=END)

        cls.other_organization = make_organization("Organização B")
        cls.other_admin = make_admin("admin.b", cls.other_organization)
        cls.other_operator = make_operator("operador.b", cls.other_organization)
        cls.other_project = make_project(cls.other_organization, "Projeto B")
        cls.other_sprint = make_sprint(cls.other_project, "Sprint B", start=START, end=END)


class SprintModelTests(ProjectsFixtureMixin, TestCase):
    def test_clean_rejects_end_before_start(self):
        sprint = Sprint(project=self.project, name="Invertida", start_date=END, end_date=START)
        with self.assertRaises(ValidationError) as context:
            sprint.full_clean()
        self.assertIn("end_date", context.exception.message_dict)

    def test_single_day_sprint_is_valid(self):
        Sprint(project=self.project, name="Um dia", start_date=START, end_date=START).full_clean()

    def test_clean_rejects_duplicated_name_in_same_project(self):
        sprint = Sprint(project=self.project, name="Sprint 1", start_date=START, end_date=END)
        with self.assertRaises(ValidationError) as context:
            sprint.full_clean()
        self.assertIn("name", context.exception.message_dict)

    def test_editing_a_sprint_does_not_conflict_with_its_own_name(self):
        self.sprint.goal = "Novo objetivo"
        self.sprint.full_clean()

    def test_same_name_is_allowed_in_another_project(self):
        project = make_project(self.organization, "Projeto C")
        Sprint(project=project, name="Sprint 1", start_date=START, end_date=END).full_clean()

    def test_database_rejects_end_before_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sprint.objects.create(project=self.project, name="Invertida", start_date=END, end_date=START)

    def test_database_rejects_duplicated_name_in_same_project(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sprint.objects.create(project=self.project, name="Sprint 1", start_date=START, end_date=END)

    def test_state_is_planned_before_start(self):
        self.assertEqual(self.sprint.state(today=date(2026, 3, 1)), Sprint.State.PLANNED)

    def test_state_is_active_on_first_and_last_day(self):
        self.assertEqual(self.sprint.state(today=START), Sprint.State.ACTIVE)
        self.assertEqual(self.sprint.state(today=date(2026, 3, 8)), Sprint.State.ACTIVE)
        self.assertEqual(self.sprint.state(today=END), Sprint.State.ACTIVE)

    def test_state_is_finished_after_end(self):
        self.assertEqual(self.sprint.state(today=date(2026, 3, 16)), Sprint.State.FINISHED)

    def test_duration_counts_both_ends(self):
        self.assertEqual(self.sprint.duration_days(), 14)

    def test_progress_is_zero_without_tasks(self):
        self.assertEqual(self.sprint.task_count(), 0)
        self.assertEqual(self.sprint.progress_percent(), 0)

    def test_progress_counts_only_done_tasks_of_the_sprint(self):
        make_task(self.project, "Feita", status=Task.Status.DONE, sprint=self.sprint)
        make_task(self.project, "Andando", status=Task.Status.IN_PROGRESS, sprint=self.sprint)
        make_task(self.project, "Pendente", sprint=self.sprint)
        make_task(self.project, "Backlog feita", status=Task.Status.DONE)
        sprint = Sprint.objects.get(pk=self.sprint.pk)
        self.assertEqual(sprint.task_count(), 3)
        self.assertEqual(sprint.completed_task_count(), 1)
        self.assertEqual(sprint.progress_percent(), 33)

    def test_str_includes_project_name(self):
        self.assertEqual(str(self.sprint), "Projeto A · Sprint 1")


class ProjectModelTests(ProjectsFixtureMixin, TestCase):
    def test_clean_rejects_due_date_before_start(self):
        project = Project(organization=self.organization, name="Errado", start_date=END, due_date=START)
        with self.assertRaises(ValidationError) as context:
            project.full_clean()
        self.assertIn("due_date", context.exception.message_dict)

    def test_progress_percent(self):
        make_task(self.project, "Feita", status=Task.Status.DONE)
        make_task(self.project, "Pendente")
        self.assertEqual(Project.objects.get(pk=self.project.pk).progress_percent(), 50)


class SprintFormTests(ProjectsFixtureMixin, TestCase):
    def test_form_rejects_duplicated_name_in_project(self):
        form = SprintForm(
            data={"name": "Sprint 1", "start_date": "2026-04-01", "end_date": "2026-04-10"}, project=self.project
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_form_rejects_end_before_start(self):
        form = SprintForm(
            data={"name": "Sprint 2", "start_date": "2026-04-10", "end_date": "2026-04-01"}, project=self.project
        )
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_form_binds_sprint_to_given_project(self):
        form = SprintForm(
            data={"name": "Sprint 2", "start_date": "2026-04-01", "end_date": "2026-04-10"}, project=self.project
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().project, self.project)


class ProjectRoleTests(ProjectsFixtureMixin, TestCase):
    project_data = {"name": "Novo projeto", "description": "", "start_date": "", "due_date": ""}

    def test_operator_sees_projects_but_no_admin_buttons(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("projects:list"))
        self.assertContains(response, "Projeto A")
        self.assertNotContains(response, reverse("projects:create"))
        self.assertNotContains(response, reverse("projects:update", args=[self.project.pk]))
        detail = self.client.get(self.project.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, reverse("projects:delete", args=[self.project.pk]))
        self.assertNotContains(detail, reverse("projects:sprint_create", args=[self.project.pk]))

    def test_admin_sees_admin_buttons(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("projects:list"))
        self.assertContains(response, reverse("projects:create"))
        detail = self.client.get(self.project.get_absolute_url())
        self.assertContains(detail, reverse("projects:delete", args=[self.project.pk]))
        self.assertContains(detail, reverse("projects:sprint_create", args=[self.project.pk]))

    def test_operator_cannot_create_project(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("projects:create")).status_code, 403)
        response = self.client.post(reverse("projects:create"), self.project_data)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Project.objects.filter(name="Novo projeto").exists())

    def test_admin_creates_project_in_own_organization(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("projects:create"), self.project_data)
        project = Project.objects.get(name="Novo projeto")
        self.assertRedirects(response, project.get_absolute_url())
        self.assertEqual(project.organization, self.organization)

    def test_operator_cannot_edit_or_delete_project(self):
        self.client.force_login(self.operator)
        update_url = reverse("projects:update", args=[self.project.pk])
        delete_url = reverse("projects:delete", args=[self.project.pk])
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.post(update_url, {**self.project_data, "name": "Hack"}).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertEqual(Project.objects.get(pk=self.project.pk).name, "Projeto A")

    def test_admin_edits_project(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("projects:update", args=[self.project.pk]), {**self.project_data, "name": "Renomeado"}
        )
        self.assertEqual(Project.objects.get(pk=self.project.pk).name, "Renomeado")

    def test_admin_deletes_project_and_its_tasks(self):
        self.client.force_login(self.admin)
        make_task(self.project, "Vai junto")
        response = self.client.post(reverse("projects:delete", args=[self.project.pk]))
        self.assertRedirects(response, reverse("projects:list"))
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertFalse(Task.objects.filter(title="Vai junto").exists())

    def test_forbidden_page_explains_admin_requirement(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("projects:create"))
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "Somente administradores", status_code=403)


class SprintRoleTests(ProjectsFixtureMixin, TestCase):
    sprint_data = {"name": "Sprint 2", "goal": "", "start_date": "2026-03-16", "end_date": "2026-03-29"}

    def test_operator_can_view_sprint_without_admin_buttons(self):
        self.client.force_login(self.operator)
        response = self.client.get(self.sprint.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("projects:sprint_update", args=[self.sprint.pk]))
        self.assertNotContains(response, reverse("projects:sprint_delete", args=[self.sprint.pk]))

    def test_operator_cannot_create_edit_or_delete_sprint(self):
        self.client.force_login(self.operator)
        create_url = reverse("projects:sprint_create", args=[self.project.pk])
        self.assertEqual(self.client.get(create_url).status_code, 403)
        self.assertEqual(self.client.post(create_url, self.sprint_data).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("projects:sprint_update", args=[self.sprint.pk]), self.sprint_data).status_code,
            403,
        )
        self.assertEqual(self.client.post(reverse("projects:sprint_delete", args=[self.sprint.pk])).status_code, 403)
        self.assertEqual(Sprint.objects.filter(project=self.project).count(), 1)

    def test_admin_creates_sprint_in_project(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("projects:sprint_create", args=[self.project.pk]), self.sprint_data)
        sprint = Sprint.objects.get(project=self.project, name="Sprint 2")
        self.assertRedirects(response, sprint.get_absolute_url())

    def test_admin_sees_form_error_for_duplicated_sprint_name(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("projects:sprint_create", args=[self.project.pk]), {**self.sprint_data, "name": "Sprint 1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)

    def test_admin_edits_sprint(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("projects:sprint_update", args=[self.sprint.pk]), self.sprint_data)
        self.assertRedirects(response, self.sprint.get_absolute_url())
        self.assertEqual(Sprint.objects.get(pk=self.sprint.pk).name, "Sprint 2")

    def test_delete_confirmation_page_is_shown_on_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("projects:sprint_delete", args=[self.sprint.pk]))
        self.assertTemplateUsed(response, "projects/sprint_confirm_delete.html")
        self.assertTrue(Sprint.objects.filter(pk=self.sprint.pk).exists())

    def test_deleting_sprint_returns_its_tasks_to_backlog(self):
        self.client.force_login(self.admin)
        task = make_task(self.project, "Na sprint", sprint=self.sprint)
        response = self.client.post(reverse("projects:sprint_delete", args=[self.sprint.pk]))
        self.assertRedirects(response, self.project.get_absolute_url())
        self.assertFalse(Sprint.objects.filter(pk=self.sprint.pk).exists())
        task.refresh_from_db()
        self.assertIsNone(task.sprint)


class ProjectIsolationTests(ProjectsFixtureMixin, TestCase):
    def test_list_shows_only_own_organization_projects(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(list(response.context["projects"]), [self.project])
        self.assertNotContains(response, "Projeto B")

    def test_project_of_another_organization_is_not_found(self):
        self.client.force_login(self.admin)
        pk = self.other_project.pk
        self.assertEqual(self.client.get(reverse("projects:detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:update", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("projects:delete", args=[pk])).status_code, 404)
        self.assertTrue(Project.objects.filter(pk=pk).exists())

    def test_operator_trying_to_edit_foreign_project_is_forbidden(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("projects:update", args=[self.other_project.pk])).status_code, 403)

    def test_sprint_of_another_organization_is_not_found(self):
        self.client.force_login(self.admin)
        pk = self.other_sprint.pk
        self.assertEqual(self.client.get(reverse("projects:sprint_detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:sprint_update", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("projects:sprint_delete", args=[pk])).status_code, 404)
        self.assertTrue(Sprint.objects.filter(pk=pk).exists())

    def test_cannot_create_sprint_in_project_of_another_organization(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("projects:sprint_create", args=[self.other_project.pk]),
            {"name": "Invasora", "start_date": "2026-04-01", "end_date": "2026-04-10"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Sprint.objects.filter(name="Invasora").exists())

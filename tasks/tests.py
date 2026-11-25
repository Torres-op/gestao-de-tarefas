from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.testing import (
    make_admin,
    make_dependency,
    make_member,
    make_operator,
    make_organization,
    make_project,
    make_sprint,
    make_subtask,
    make_task,
    messages_of,
)

from .forms import SubtaskForm, TaskDependencyForm, TaskForm
from .models import Subtask, Task, TaskDependency

DONE = Task.Status.DONE
DOING = Task.Status.IN_PROGRESS
TODO = Task.Status.PENDING


def task_form_data(task, **overrides):
    data = {
        "project": task.project_id,
        "sprint": task.sprint_id or "",
        "title": task.title,
        "description": task.description,
        "assignee": task.assignee_id or "",
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else "",
    }
    data.update(overrides)
    return data


def reload(instance):
    instance.refresh_from_db()
    return instance


class OrganizationFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Organização A")
        cls.admin = make_admin("admin.a", cls.organization)
        cls.operator = make_operator("operador.a", cls.organization)
        cls.project = make_project(cls.organization, "Projeto A")


class TaskTimestampTests(OrganizationFixtureMixin, TestCase):
    def test_new_pending_task_has_no_timestamps(self):
        task = make_task(self.project, "Pendente")
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.completed_at)

    def test_moving_to_in_progress_fills_started_at_only(self):
        task = make_task(self.project, "Em andamento")
        task.status = DOING
        task.save()
        self.assertIsNotNone(task.started_at)
        self.assertIsNone(task.completed_at)

    def test_task_created_directly_as_done_gets_started_at_equal_to_completed_at(self):
        task = make_task(self.project, "Concluída direto", status=DONE)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.started_at, task.completed_at)

    def test_completing_keeps_original_started_at(self):
        task = make_task(self.project, "Fluxo", status=DOING)
        started_at = task.started_at
        task.complete()
        task = reload(task)
        self.assertEqual(task.started_at, started_at)
        self.assertIsNotNone(task.completed_at)
        self.assertGreaterEqual(task.completed_at, started_at)

    def test_saving_a_done_task_again_does_not_overwrite_completed_at(self):
        task = make_task(self.project, "Concluída", status=DONE)
        completed_at = task.completed_at
        task.title = "Concluída e renomeada"
        task.save()
        self.assertEqual(reload(task).completed_at, completed_at)

    def test_reopening_clears_completed_at_but_keeps_started_at(self):
        task = make_task(self.project, "Reaberta", status=DONE)
        started_at = task.started_at
        task.reopen()
        task = reload(task)
        self.assertEqual(task.status, DOING)
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.started_at, started_at)

    def test_returning_to_pending_clears_started_at(self):
        task = make_task(self.project, "Volta", status=DOING)
        task.status = TODO
        task.save()
        task = reload(task)
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.completed_at)


class DependencyInvariantModelTests(OrganizationFixtureMixin, TestCase):
    def test_a1_complete_with_pending_dependency_raises_and_keeps_status(self):
        requirement = make_task(self.project, "Requisitos")
        task = make_task(self.project, "Modelagem", status=DOING)
        make_dependency(task, requirement)
        with self.assertRaises(ValidationError):
            task.complete()
        self.assertEqual(reload(task).status, DOING)
        self.assertIsNone(task.completed_at)

    def test_a1_complete_succeeds_once_dependency_is_done(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        task = make_task(self.project, "Modelagem")
        make_dependency(task, requirement)
        task.complete()
        self.assertEqual(reload(task).status, DONE)

    def test_a1_clean_rejects_done_status_with_pending_dependency(self):
        requirement = make_task(self.project, "Requisitos")
        task = make_task(self.project, "Modelagem")
        make_dependency(task, requirement)
        task.status = DONE
        with self.assertRaises(ValidationError) as context:
            task.full_clean()
        self.assertIn("status", context.exception.message_dict)

    def test_a2_reopen_prerequisite_of_done_task_raises(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        task = make_task(self.project, "Modelagem", status=DONE)
        make_dependency(task, requirement)
        with self.assertRaises(ValidationError):
            requirement.reopen()
        self.assertEqual(reload(requirement).status, DONE)

    def test_a2_reopen_prerequisite_is_allowed_when_dependent_is_open(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        task = make_task(self.project, "Modelagem", status=DOING)
        make_dependency(task, requirement)
        requirement.reopen()
        self.assertEqual(reload(requirement).status, DOING)

    def test_a2_clean_rejects_moving_prerequisite_of_done_task_out_of_done(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        task = make_task(self.project, "Modelagem", status=DONE)
        make_dependency(task, requirement)
        requirement.status = TODO
        with self.assertRaises(ValidationError) as context:
            requirement.full_clean()
        self.assertIn("status", context.exception.message_dict)

    def test_a3_dependency_from_done_task_to_pending_task_is_rejected(self):
        done = make_task(self.project, "Concluída", status=DONE)
        pending = make_task(self.project, "Pendente")
        dependency = TaskDependency(task=done, depends_on=pending)
        with self.assertRaises(ValidationError) as context:
            dependency.full_clean()
        self.assertIn("depends_on", context.exception.message_dict)

    def test_a3_dependency_between_two_done_tasks_is_allowed(self):
        done = make_task(self.project, "Concluída", status=DONE)
        other = make_task(self.project, "Outra concluída", status=DONE)
        TaskDependency(task=done, depends_on=other).full_clean()

    def test_new_task_clean_skips_blocking_checks(self):
        task = Task(project=self.project, title="Nova", status=DONE)
        task.full_clean()


class SubtaskInvariantModelTests(OrganizationFixtureMixin, TestCase):
    def test_b1_complete_with_open_subtask_raises(self):
        task = make_task(self.project, "Telas", status=DOING)
        make_subtask(task, "Wireframe")
        with self.assertRaises(ValidationError):
            task.complete()
        self.assertEqual(reload(task).status, DOING)

    def test_b1_complete_succeeds_when_all_subtasks_are_done(self):
        task = make_task(self.project, "Telas", status=DOING)
        make_subtask(task, "Wireframe", is_done=True)
        task.complete()
        self.assertEqual(reload(task).status, DONE)

    def test_b1_clean_rejects_done_status_with_open_subtask(self):
        task = make_task(self.project, "Telas")
        make_subtask(task, "Wireframe")
        task.status = DONE
        with self.assertRaises(ValidationError) as context:
            task.full_clean()
        self.assertIn("status", context.exception.message_dict)

    def test_b2_toggle_cannot_reopen_subtask_of_done_task(self):
        task = make_task(self.project, "Telas", status=DOING)
        subtask = make_subtask(task, "Wireframe", is_done=True)
        task.complete()
        subtask = Subtask.objects.get(pk=subtask.pk)
        with self.assertRaises(ValidationError):
            subtask.toggle()
        self.assertTrue(reload(subtask).is_done)

    def test_b2_toggle_works_both_ways_on_open_task(self):
        task = make_task(self.project, "Telas", status=DOING)
        subtask = make_subtask(task, "Wireframe")
        subtask.toggle()
        self.assertTrue(reload(subtask).is_done)
        subtask.toggle()
        self.assertFalse(reload(subtask).is_done)

    def test_b2_clean_rejects_reopening_subtask_of_done_task(self):
        task = make_task(self.project, "Telas", status=DONE)
        subtask = make_subtask(task, "Wireframe", is_done=True)
        subtask.is_done = False
        with self.assertRaises(ValidationError) as context:
            subtask.full_clean()
        self.assertIn("is_done", context.exception.message_dict)

    def test_b3_open_subtask_cannot_be_added_to_done_task(self):
        task = make_task(self.project, "Telas", status=DONE)
        with self.assertRaises(ValidationError) as context:
            Subtask(task=task, title="Atrasada").full_clean()
        self.assertIn("is_done", context.exception.message_dict)

    def test_b3_done_subtask_can_be_added_to_done_task(self):
        task = make_task(self.project, "Telas", status=DONE)
        Subtask(task=task, title="Já feita", is_done=True).full_clean()


class BlockingReasonMessageTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.task = make_task(self.project, "Principal", status=DOING)

    def test_unblocked_task_has_empty_reason(self):
        self.assertEqual(self.task.blocking_reason(), "")
        self.assertFalse(self.task.is_blocked())

    def test_single_pending_dependency_uses_singular(self):
        make_dependency(self.task, make_task(self.project, "Requisitos"))
        self.assertEqual(
            self.task.blocking_reason(),
            'Ela depende da tarefa "Requisitos", que ainda não foi concluída.',
        )
        self.assertTrue(self.task.is_blocked())

    def test_several_pending_dependencies_use_plural(self):
        make_dependency(self.task, make_task(self.project, "Alfa"))
        make_dependency(self.task, make_task(self.project, "Beta"))
        self.assertEqual(
            self.task.blocking_reason(),
            'Ela depende das tarefas "Alfa", "Beta", que ainda não foram concluídas.',
        )

    def test_done_dependencies_are_not_listed(self):
        make_dependency(self.task, make_task(self.project, "Alfa", status=DONE))
        make_dependency(self.task, make_task(self.project, "Beta"))
        self.assertEqual(
            self.task.blocking_reason(),
            'Ela depende da tarefa "Beta", que ainda não foi concluída.',
        )

    def test_single_open_subtask_uses_singular(self):
        make_subtask(self.task, "Wireframe")
        make_subtask(self.task, "Já feita", is_done=True)
        self.assertEqual(self.task.blocking_reason(), 'A subtarefa "Wireframe" ainda não foi concluída.')

    def test_several_open_subtasks_use_plural(self):
        make_subtask(self.task, "Wireframe")
        make_subtask(self.task, "Protótipo")
        self.assertEqual(
            self.task.blocking_reason(),
            'As subtarefas "Wireframe", "Protótipo" ainda não foram concluídas.',
        )

    def test_dependencies_and_subtasks_are_combined_in_one_message(self):
        make_dependency(self.task, make_task(self.project, "Requisitos"))
        make_subtask(self.task, "Wireframe")
        self.assertEqual(
            self.task.blocking_reason(),
            'Ela depende da tarefa "Requisitos", que ainda não foi concluída. '
            'A subtarefa "Wireframe" ainda não foi concluída.',
        )

    def test_reopening_reason_singular_and_plural(self):
        requirement = make_task(self.project, "Base", status=DONE)
        make_dependency(make_task(self.project, "Alfa", status=DONE), requirement)
        self.assertEqual(
            requirement.reopening_reason(), 'A tarefa "Alfa" depende desta e já está concluída.'
        )
        make_dependency(make_task(self.project, "Beta", status=DONE), requirement)
        self.assertEqual(
            requirement.reopening_reason(),
            'As tarefas "Alfa", "Beta" dependem desta e já estão concluídas.',
        )


class DependencyValidationTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.alpha = make_task(self.project, "Alfa")
        self.beta = make_task(self.project, "Beta")
        self.gamma = make_task(self.project, "Gama")

    def assertDependencyError(self, task, depends_on, fragment):
        with self.assertRaises(ValidationError) as context:
            TaskDependency(task=task, depends_on=depends_on).full_clean()
        self.assertIn(fragment, " ".join(context.exception.message_dict["depends_on"]))

    def test_self_dependency_is_rejected_by_clean(self):
        self.assertDependencyError(self.alpha, self.alpha, "não pode depender dela mesma")

    def test_self_dependency_is_rejected_by_database_check_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskDependency.objects.create(task=self.alpha, depends_on=self.alpha)

    def test_dependency_on_task_of_another_project_is_rejected(self):
        other = make_task(make_project(self.organization, "Outro projeto"), "Externa")
        self.assertDependencyError(self.alpha, other, "mesmo projeto")

    def test_duplicate_dependency_is_rejected_by_clean(self):
        make_dependency(self.alpha, self.beta)
        self.assertDependencyError(self.alpha, self.beta, "já foi cadastrada")

    def test_duplicate_dependency_is_rejected_by_database_unique_constraint(self):
        make_dependency(self.alpha, self.beta)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskDependency.objects.create(task=self.alpha, depends_on=self.beta)

    def test_direct_cycle_is_rejected(self):
        make_dependency(self.alpha, self.beta)
        self.assertDependencyError(self.beta, self.alpha, "ciclo")

    def test_transitive_cycle_is_rejected(self):
        make_dependency(self.alpha, self.beta)
        make_dependency(self.beta, self.gamma)
        self.assertDependencyError(self.gamma, self.alpha, "ciclo")

    def test_diamond_shape_is_not_a_cycle(self):
        delta = make_task(self.project, "Delta")
        make_dependency(self.alpha, self.beta)
        make_dependency(self.alpha, self.gamma)
        make_dependency(self.beta, delta)
        TaskDependency(task=self.gamma, depends_on=delta).full_clean()
        self.assertFalse(TaskDependency(task=self.gamma, depends_on=delta).creates_cycle())


class ValidateRelationsTests(OrganizationFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_project = make_project(cls.organization, "Projeto B")
        cls.sprint = make_sprint(cls.project, "Sprint A")
        cls.other_sprint = make_sprint(cls.other_project, "Sprint B")
        cls.member = make_member(cls.organization, "Ana")
        cls.foreign_member = make_member(make_organization("Organização Z"), "Zeca")

    def test_sprint_and_assignee_of_same_scope_are_accepted(self):
        Task(project=self.project, title="Ok", sprint=self.sprint, assignee=self.member).validate_relations()

    def test_sprint_of_another_project_is_rejected(self):
        task = Task(project=self.project, title="Errada", sprint=self.other_sprint)
        with self.assertRaises(ValidationError) as context:
            task.full_clean()
        self.assertIn("sprint", context.exception.message_dict)

    def test_assignee_of_another_organization_is_rejected(self):
        task = Task(project=self.project, title="Errada", assignee=self.foreign_member)
        with self.assertRaises(ValidationError) as context:
            task.full_clean()
        self.assertIn("assignee", context.exception.message_dict)

    def test_task_form_rejects_sprint_of_another_project_of_same_organization(self):
        task = make_task(self.project, "Existente")
        form = TaskForm(
            data=task_form_data(task, sprint=self.other_sprint.pk), instance=task, organization=self.organization
        )
        self.assertFalse(form.is_valid())
        self.assertIn("sprint", form.errors)

    def test_task_form_rejects_assignee_of_another_organization_as_invalid_choice(self):
        task = make_task(self.project, "Existente")
        form = TaskForm(
            data=task_form_data(task, assignee=self.foreign_member.pk), instance=task, organization=self.organization
        )
        self.assertFalse(form.is_valid())
        self.assertIn("assignee", form.errors)


class TaskActionHttpTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.operator)

    def test_get_on_complete_or_reopen_is_not_allowed(self):
        task = make_task(self.project, "Qualquer")
        self.assertEqual(self.client.get(reverse("tasks:complete", args=[task.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("tasks:reopen", args=[task.pk])).status_code, 405)

    def test_a1_complete_view_blocks_and_explains_pending_dependency(self):
        requirement = make_task(self.project, "Requisitos")
        task = make_task(self.project, "Modelagem")
        make_dependency(task, requirement)
        response = self.client.post(reverse("tasks:complete", args=[task.pk]))
        self.assertRedirects(response, task.get_absolute_url())
        self.assertEqual(reload(task).status, TODO)
        [message] = messages_of(response)
        self.assertIn('Não é possível concluir "Modelagem"', message)
        self.assertIn('"Requisitos"', message)

    def test_b1_complete_view_blocks_and_explains_open_subtask(self):
        task = make_task(self.project, "Telas", status=DOING)
        make_subtask(task, "Wireframe")
        response = self.client.post(reverse("tasks:complete", args=[task.pk]))
        self.assertEqual(reload(task).status, DOING)
        self.assertIn('A subtarefa "Wireframe" ainda não foi concluída.', messages_of(response)[0])

    def test_complete_view_concludes_unblocked_task(self):
        task = make_task(self.project, "Livre", status=DOING)
        response = self.client.post(reverse("tasks:complete", args=[task.pk]))
        self.assertRedirects(response, task.get_absolute_url())
        self.assertEqual(reload(task).status, DONE)
        self.assertEqual(messages_of(response), ['Tarefa "Livre" concluída.'])

    def test_a2_reopen_view_blocks_prerequisite_of_done_task(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        task = make_task(self.project, "Modelagem", status=DONE)
        make_dependency(task, requirement)
        response = self.client.post(reverse("tasks:reopen", args=[requirement.pk]))
        self.assertEqual(reload(requirement).status, DONE)
        message = messages_of(response)[0]
        self.assertIn('Não é possível reabrir "Requisitos"', message)
        self.assertIn('A tarefa "Modelagem" depende desta', message)

    def test_reopen_view_reopens_task_without_done_dependents(self):
        task = make_task(self.project, "Reabrir", status=DONE)
        self.client.post(reverse("tasks:reopen", args=[task.pk]))
        self.assertEqual(reload(task).status, DOING)

    def test_cascade_unblocks_in_the_right_order(self):
        requirement = make_task(self.project, "Requisitos")
        task = make_task(self.project, "Modelagem")
        make_dependency(task, requirement)
        self.client.post(reverse("tasks:complete", args=[requirement.pk]))
        self.client.post(reverse("tasks:complete", args=[task.pk]))
        self.assertEqual(reload(requirement).status, DONE)
        self.assertEqual(reload(task).status, DONE)


class TaskFormStatusHttpTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.operator)

    def post_edit(self, task, **overrides):
        return self.client.post(reverse("tasks:update", args=[task.pk]), task_form_data(task, **overrides))

    def test_a1_edit_form_cannot_set_done_with_pending_dependency(self):
        requirement = make_task(self.project, "Requisitos")
        task = make_task(self.project, "Modelagem")
        make_dependency(task, requirement)
        response = self.post_edit(task, status=DONE)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Requisitos", " ".join(response.context["form"].errors["status"]))
        self.assertEqual(reload(task).status, TODO)

    def test_b1_edit_form_cannot_set_done_with_open_subtask(self):
        task = make_task(self.project, "Telas")
        make_subtask(task, "Wireframe")
        response = self.post_edit(task, status=DONE)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Wireframe", " ".join(response.context["form"].errors["status"]))
        self.assertEqual(reload(task).status, TODO)

    def test_a2_edit_form_cannot_reopen_prerequisite_of_done_task(self):
        requirement = make_task(self.project, "Requisitos", status=DONE)
        make_dependency(make_task(self.project, "Modelagem", status=DONE), requirement)
        response = self.post_edit(requirement, status=DOING)
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)
        self.assertEqual(reload(requirement).status, DONE)

    def test_edit_form_concludes_unblocked_task_and_fills_timestamps(self):
        task = make_task(self.project, "Livre")
        response = self.post_edit(task, status=DONE)
        self.assertRedirects(response, task.get_absolute_url())
        task = reload(task)
        self.assertEqual(task.status, DONE)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.started_at, task.completed_at)


class SubtaskHttpTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.operator)
        self.task = make_task(self.project, "Telas", status=DOING)
        self.subtask = make_subtask(self.task, "Wireframe", is_done=True)
        self.task.complete()

    def test_toggle_requires_post(self):
        response = self.client.get(reverse("tasks:subtask_toggle", args=[self.subtask.pk]))
        self.assertEqual(response.status_code, 405)

    def test_b2_toggle_view_refuses_to_reopen_subtask_of_done_task(self):
        response = self.client.post(reverse("tasks:subtask_toggle", args=[self.subtask.pk]))
        self.assertRedirects(response, self.task.get_absolute_url())
        self.assertTrue(reload(self.subtask).is_done)
        self.assertIn('Não é possível reabrir a subtarefa "Wireframe"', messages_of(response)[0])

    def test_toggle_view_reopens_subtask_after_task_is_reopened(self):
        self.task.reopen()
        self.client.post(reverse("tasks:subtask_toggle", args=[self.subtask.pk]))
        self.assertFalse(reload(self.subtask).is_done)

    def test_b2_subtask_edit_form_refuses_to_reopen_subtask_of_done_task(self):
        response = self.client.post(
            reverse("tasks:subtask_update", args=[self.subtask.pk]), {"title": "Wireframe"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_done", response.context["form"].errors)
        self.assertTrue(reload(self.subtask).is_done)

    def test_b3_subtask_form_refuses_open_subtask_on_done_task(self):
        form = SubtaskForm(data={"title": "Nova"}, task=self.task)
        self.assertFalse(form.is_valid())
        self.assertIn("is_done", form.errors)

    def test_b3_create_view_refuses_open_subtask_on_done_task(self):
        response = self.client.post(reverse("tasks:subtask_create", args=[self.task.pk]), {"title": "Nova"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_done", response.context["form"].errors)
        self.assertEqual(self.task.subtasks.count(), 1)

    def test_create_view_accepts_done_subtask_on_done_task(self):
        response = self.client.post(
            reverse("tasks:subtask_create", args=[self.task.pk]), {"title": "Já feita", "is_done": "on"}
        )
        self.assertRedirects(response, self.task.get_absolute_url())
        self.assertEqual(self.task.subtasks.count(), 2)

    def test_deleting_subtask_of_done_task_is_allowed(self):
        response = self.client.post(reverse("tasks:subtask_delete", args=[self.subtask.pk]))
        self.assertRedirects(response, self.task.get_absolute_url())
        self.assertFalse(Subtask.objects.filter(pk=self.subtask.pk).exists())


class DependencyFormHttpTests(OrganizationFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.operator)
        self.alpha = make_task(self.project, "Alfa")
        self.beta = make_task(self.project, "Beta")

    def post_dependency(self, task, depends_on):
        return self.client.post(
            reverse("tasks:dependency_create", args=[task.pk]), {"depends_on": depends_on.pk}
        )

    def test_creates_valid_dependency(self):
        response = self.post_dependency(self.alpha, self.beta)
        self.assertRedirects(response, self.alpha.get_absolute_url())
        self.assertTrue(TaskDependency.objects.filter(task=self.alpha, depends_on=self.beta).exists())

    def test_queryset_offers_only_same_project_tasks_not_self_and_not_already_required(self):
        gamma = make_task(self.project, "Gama")
        make_task(make_project(self.organization, "Outro"), "Externa")
        make_dependency(self.alpha, gamma)
        form = TaskDependencyForm(task=self.alpha)
        self.assertEqual(list(form.fields["depends_on"].queryset), [self.beta])

    def test_a3_form_refuses_dependency_from_done_task_to_pending_task(self):
        done = make_task(self.project, "Concluída", status=DONE)
        response = self.post_dependency(done, self.beta)
        self.assertEqual(response.status_code, 200)
        self.assertIn("já está concluída", " ".join(response.context["form"].errors["depends_on"]))
        self.assertFalse(TaskDependency.objects.filter(task=done).exists())

    def test_form_refuses_cycle_with_specific_message(self):
        make_dependency(self.beta, self.alpha)
        response = self.post_dependency(self.alpha, self.beta)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ciclo", " ".join(response.context["form"].errors["depends_on"]))

    def test_forged_self_dependency_is_rejected_as_invalid_choice(self):
        response = self.post_dependency(self.alpha, self.alpha)
        self.assertEqual(response.status_code, 200)
        self.assertIn("depends_on", response.context["form"].errors)
        self.assertFalse(TaskDependency.objects.exists())

    def test_forged_dependency_on_other_project_is_rejected(self):
        external = make_task(make_project(self.organization, "Outro"), "Externa")
        response = self.post_dependency(self.alpha, external)
        self.assertIn("depends_on", response.context["form"].errors)

    def test_forged_duplicate_dependency_is_rejected(self):
        make_dependency(self.alpha, self.beta)
        response = self.post_dependency(self.alpha, self.beta)
        self.assertIn("depends_on", response.context["form"].errors)
        self.assertEqual(TaskDependency.objects.count(), 1)

    def test_removing_dependency_unblocks_task(self):
        dependency = make_dependency(self.alpha, self.beta)
        self.client.post(reverse("tasks:dependency_delete", args=[dependency.pk]))
        self.assertFalse(Task.objects.get(pk=self.alpha.pk).is_blocked())


class TaskRoleTests(OrganizationFixtureMixin, TestCase):
    def test_operator_can_create_task(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("tasks:create"), {"project": self.project.pk, "title": "Criada", "status": TODO}
        )
        task = Task.objects.get(title="Criada")
        self.assertRedirects(response, task.get_absolute_url())

    def test_operator_can_edit_task(self):
        self.client.force_login(self.operator)
        task = make_task(self.project, "Antiga")
        self.client.post(reverse("tasks:update", args=[task.pk]), task_form_data(task, title="Nova"))
        self.assertEqual(reload(task).title, "Nova")

    def test_operator_cannot_delete_task(self):
        self.client.force_login(self.operator)
        task = make_task(self.project, "Protegida")
        self.assertEqual(self.client.get(reverse("tasks:delete", args=[task.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("tasks:delete", args=[task.pk])).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_admin_can_delete_task(self):
        self.client.force_login(self.admin)
        task = make_task(self.project, "Descartável")
        response = self.client.post(reverse("tasks:delete", args=[task.pk]))
        self.assertRedirects(response, self.project.get_absolute_url())
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_delete_button_is_shown_only_to_admin(self):
        task = make_task(self.project, "Botões")
        delete_url = reverse("tasks:delete", args=[task.pk])
        self.client.force_login(self.operator)
        self.assertNotContains(self.client.get(task.get_absolute_url()), delete_url)
        self.assertNotContains(self.client.get(reverse("tasks:list")), delete_url)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(task.get_absolute_url()), delete_url)
        self.assertContains(self.client.get(reverse("tasks:list")), delete_url)


class TaskListTests(OrganizationFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_project = make_project(cls.organization, "Projeto B")
        cls.sprint = make_sprint(cls.project, "Sprint 1")
        cls.member = make_member(cls.organization, "Ana")
        cls.in_sprint = make_task(cls.project, "No sprint", status=DOING, sprint=cls.sprint)
        cls.backlog = make_task(cls.project, "Backlog")
        cls.other = make_task(cls.other_project, "Outro projeto", status=DONE)
        cls.foreign = make_task(make_project(make_organization("Organização Z"), "Projeto Z"), "Estrangeira")

    def setUp(self):
        self.client.force_login(self.operator)

    def listed(self, **params):
        response = self.client.get(reverse("tasks:list"), params)
        self.assertEqual(response.status_code, 200)
        return {task.title for task in response.context["tasks"]}

    def test_lists_all_tasks_of_the_organization_only(self):
        self.assertEqual(self.listed(), {"No sprint", "Backlog", "Outro projeto"})

    def test_filters_by_project(self):
        self.assertEqual(self.listed(project=self.other_project.pk), {"Outro projeto"})

    def test_filters_by_sprint(self):
        self.assertEqual(self.listed(sprint=self.sprint.pk), {"No sprint"})

    def test_filters_by_status(self):
        self.assertEqual(self.listed(status=TODO), {"Backlog"})
        self.assertEqual(self.listed(status=DONE), {"Outro projeto"})

    def test_combines_filters(self):
        self.assertEqual(self.listed(project=self.project.pk, status=DOING), {"No sprint"})

    def test_invalid_filter_values_are_ignored(self):
        self.assertEqual(self.listed(project="abc", sprint="-1", status="archived"), {"No sprint", "Backlog", "Outro projeto"})

    def test_filtering_by_foreign_project_does_not_leak_tasks(self):
        self.assertEqual(self.listed(project=self.foreign.project_id), set())

    def test_filter_selects_only_offer_organization_options(self):
        response = self.client.get(reverse("tasks:list"))
        self.assertEqual(set(response.context["projects"]), {self.project, self.other_project})
        self.assertEqual(list(response.context["sprints"]), [self.sprint])

    def test_list_shows_blocked_badge_and_blocking_task(self):
        make_dependency(self.backlog, self.in_sprint)
        response = self.client.get(reverse("tasks:list"))
        self.assertContains(response, "row-blocked")
        self.assertContains(response, "Bloqueada por:")

    def count_list_queries(self):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(reverse("tasks:list"))
        self.assertEqual(response.status_code, 200)
        return len(context.captured_queries)

    def add_rich_tasks(self, amount, offset):
        previous = self.backlog
        for index in range(offset, offset + amount):
            task = make_task(
                self.project, f"Extra {index}", status=DOING, sprint=self.sprint, assignee=self.member,
                due_date=date(2026, 3, 1) + timedelta(days=index),
            )
            make_subtask(task, f"Sub {index}")
            make_subtask(task, f"Sub feita {index}", is_done=True)
            make_dependency(task, previous)
            previous = task

    def test_list_uses_fixed_number_of_queries_regardless_of_task_count(self):
        self.add_rich_tasks(3, 0)
        self.count_list_queries()
        small = self.count_list_queries()
        self.add_rich_tasks(10, 3)
        large = self.count_list_queries()
        self.assertEqual(small, large)
        self.assertLessEqual(large, 15)

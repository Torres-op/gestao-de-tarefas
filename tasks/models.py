from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from projects.models import Project


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        IN_PROGRESS = "in_progress", "Em andamento"
        DONE = "done", "Concluída"

    project = models.ForeignKey(
        Project,
        verbose_name="Projeto",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    assignee = models.ForeignKey(
        Member,
        verbose_name="Responsável",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    title = models.CharField("Título", max_length=150)
    description = models.TextField("Descrição", blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.PENDING)
    due_date = models.DateField("Prazo", null=True, blank=True)
    completed_at = models.DateTimeField("Concluída em", null=True, blank=True)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizada em", auto_now=True)

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"
        ordering = ["due_date", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("tasks:detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != self.Status.DONE:
            self.completed_at = None
        super().save(*args, **kwargs)

    def clean(self):
        if not self.pk:
            return
        if self.status == self.Status.DONE:
            reason = self.blocking_reason()
        else:
            reason = self.reopening_reason()
        if reason:
            raise ValidationError({"status": reason})

    def pending_dependencies(self):
        return [
            dependency.depends_on
            for dependency in self.dependencies.all()
            if dependency.depends_on.status != self.Status.DONE
        ]

    def completed_dependents(self):
        return [
            dependency.task
            for dependency in self.dependents.all()
            if dependency.task.status == self.Status.DONE
        ]

    def is_blocked(self):
        return bool(self.pending_dependencies()) or bool(self.pending_subtasks())

    def blocking_reason(self):
        reasons = []

        pending_tasks = self.pending_dependencies()
        if pending_tasks:
            titles = ", ".join(f'"{task.title}"' for task in pending_tasks)
            if len(pending_tasks) == 1:
                reasons.append(f"Ela depende da tarefa {titles}, que ainda não foi concluída.")
            else:
                reasons.append(f"Ela depende das tarefas {titles}, que ainda não foram concluídas.")

        open_subtasks = self.pending_subtasks()
        if open_subtasks:
            titles = ", ".join(f'"{subtask.title}"' for subtask in open_subtasks)
            if len(open_subtasks) == 1:
                reasons.append(f"A subtarefa {titles} ainda não foi concluída.")
            else:
                reasons.append(f"As subtarefas {titles} ainda não foram concluídas.")

        return " ".join(reasons)

    def reopening_reason(self):
        dependents = self.completed_dependents()
        if not dependents:
            return ""
        titles = ", ".join(f'"{task.title}"' for task in dependents)
        if len(dependents) == 1:
            return f"A tarefa {titles} depende desta e já está concluída."
        return f"As tarefas {titles} dependem desta e já estão concluídas."

    def complete(self):
        reason = self.blocking_reason()
        if reason:
            raise ValidationError(reason)
        self.status = self.Status.DONE
        self.save()

    def reopen(self):
        reason = self.reopening_reason()
        if reason:
            raise ValidationError(reason)
        self.status = self.Status.IN_PROGRESS
        self.save()

    def is_done(self):
        return self.status == self.Status.DONE

    def is_in_progress(self):
        return self.status == self.Status.IN_PROGRESS

    def subtask_count(self):
        return len(self.subtasks.all())

    def pending_subtasks(self):
        return [subtask for subtask in self.subtasks.all() if not subtask.is_done]

    def completed_subtask_count(self):
        return len([subtask for subtask in self.subtasks.all() if subtask.is_done])

    def subtask_progress_percent(self):
        total = self.subtask_count()
        if not total:
            return 0
        return round(self.completed_subtask_count() * 100 / total)


class Subtask(models.Model):
    task = models.ForeignKey(
        Task,
        verbose_name="Tarefa",
        on_delete=models.CASCADE,
        related_name="subtasks",
    )
    title = models.CharField("Título", max_length=150)
    is_done = models.BooleanField("Concluída", default=False)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Subtarefa"
        verbose_name_plural = "Subtarefas"
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.task.get_absolute_url()

    def clean(self):
        if self.task_id is None or self.is_done:
            return
        reason = self.reopening_reason()
        if reason:
            raise ValidationError({"is_done": reason})

    def reopening_reason(self):
        if self.task.is_done():
            return (
                f'A tarefa "{self.task.title}" já está concluída. '
                "Reabra a tarefa antes de deixar uma subtarefa em aberto."
            )
        return ""

    def toggle(self):
        if self.is_done:
            reason = self.reopening_reason()
            if reason:
                raise ValidationError(reason)
        self.is_done = not self.is_done
        self.save()


class TaskDependency(models.Model):
    task = models.ForeignKey(
        Task,
        verbose_name="Tarefa dependente",
        on_delete=models.CASCADE,
        related_name="dependencies",
    )
    depends_on = models.ForeignKey(
        Task,
        verbose_name="Depende da tarefa",
        on_delete=models.CASCADE,
        related_name="dependents",
    )
    created_at = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Dependência"
        verbose_name_plural = "Dependências"
        ordering = ["depends_on__title"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "depends_on"],
                name="unique_task_dependency",
            ),
            models.CheckConstraint(
                condition=~models.Q(task=models.F("depends_on")),
                name="prevent_self_dependency",
            ),
        ]

    def __str__(self):
        return f"{self.task} depende de {self.depends_on}"

    def clean(self):
        if self.task_id is None or self.depends_on_id is None:
            return

        if self.task_id == self.depends_on_id:
            raise ValidationError({"depends_on": "Uma tarefa não pode depender dela mesma."})

        if self.task.project_id != self.depends_on.project_id:
            raise ValidationError({"depends_on": "A dependência precisa ser uma tarefa do mesmo projeto."})

        duplicated = TaskDependency.objects.filter(
            task_id=self.task_id, depends_on_id=self.depends_on_id
        ).exclude(pk=self.pk)
        if duplicated.exists():
            raise ValidationError({"depends_on": "Esta dependência já foi cadastrada."})

        if self.task.status == Task.Status.DONE and self.depends_on.status != Task.Status.DONE:
            raise ValidationError(
                {"depends_on": f'A tarefa "{self.task.title}" já está concluída e não pode passar a depender de uma tarefa pendente.'}
            )

        if self.creates_cycle():
            raise ValidationError({"depends_on": "Esta dependência criaria um ciclo entre as tarefas."})

    def creates_cycle(self):
        visited = set()
        pending = [self.task_id]
        while pending:
            current = pending.pop()
            if current == self.depends_on_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                TaskDependency.objects.filter(depends_on_id=current).values_list("task_id", flat=True)
            )
        return False

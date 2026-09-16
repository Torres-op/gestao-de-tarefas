from django.db import models
from django.urls import reverse

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

    def is_done(self):
        return self.status == self.Status.DONE

    def is_in_progress(self):
        return self.status == self.Status.IN_PROGRESS

    def subtask_count(self):
        return len(self.subtasks.all())

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

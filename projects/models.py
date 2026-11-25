from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import OrganizationOwned

MAX_SPRINT_DAYS = 60


class Project(OrganizationOwned):
    name = models.CharField("Nome", max_length=120)
    description = models.TextField("Descrição", blank=True)
    start_date = models.DateField("Data de início", null=True, blank=True)
    due_date = models.DateField("Prazo final", null=True, blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"pk": self.pk})

    def task_count(self):
        return len(self.tasks.all())

    def completed_task_count(self):
        return len([task for task in self.tasks.all() if task.status == task.Status.DONE])

    def progress_percent(self):
        total = self.task_count()
        if not total:
            return 0
        return round(self.completed_task_count() * 100 / total)

    def clean(self):
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({"due_date": "O prazo final não pode ser anterior à data de início."})


class Sprint(models.Model):
    class State(models.TextChoices):
        PLANNED = "planned", "Planejada"
        ACTIVE = "active", "Em andamento"
        FINISHED = "finished", "Encerrada"

    project = models.ForeignKey(
        Project,
        verbose_name="Projeto",
        on_delete=models.CASCADE,
        related_name="sprints",
    )
    name = models.CharField("Nome", max_length=80)
    goal = models.TextField("Objetivo", blank=True)
    start_date = models.DateField("Início")
    end_date = models.DateField("Fim")
    created_at = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Sprint"
        verbose_name_plural = "Sprints"
        ordering = ["project__name", "start_date"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_sprint_name_per_project"),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="sprint_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__lte=models.F("start_date") + timedelta(days=MAX_SPRINT_DAYS - 1)),
                name="sprint_max_duration",
            ),
        ]

    def __str__(self):
        return f"{self.project.name} · {self.name}"

    def get_absolute_url(self):
        return reverse("projects:sprint_detail", kwargs={"pk": self.pk})

    def clean(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({"end_date": "O fim da sprint não pode ser anterior ao início."})
            if self.duration_days() > MAX_SPRINT_DAYS:
                raise ValidationError({"end_date": f"Uma sprint pode durar no máximo {MAX_SPRINT_DAYS} dias."})
        if self.pk and self.changed_project() and self.tasks.exists():
            raise ValidationError(
                {"project": "Uma sprint com tarefas não pode mudar de projeto. Mova as tarefas antes."}
            )
        if self.project_id and self.name:
            duplicated = Sprint.objects.filter(project_id=self.project_id, name=self.name).exclude(pk=self.pk)
            if duplicated.exists():
                raise ValidationError({"name": "Já existe uma sprint com este nome neste projeto."})

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_project_id = instance.__dict__.get("project_id")
        return instance

    def changed_project(self):
        original_project_id = getattr(self, "_loaded_project_id", None)
        if original_project_id is None:
            original_project_id = Sprint.objects.filter(pk=self.pk).values_list("project_id", flat=True).first()
        return original_project_id is not None and original_project_id != self.project_id

    def state(self, today=None):
        today = today or timezone.localdate()
        if today < self.start_date:
            return self.State.PLANNED
        if today > self.end_date:
            return self.State.FINISHED
        return self.State.ACTIVE

    def state_label(self):
        return self.State(self.state()).label

    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    def task_count(self):
        return len(self.tasks.all())

    def completed_task_count(self):
        return len([task for task in self.tasks.all() if task.status == task.Status.DONE])

    def progress_percent(self):
        total = self.task_count()
        if not total:
            return 0
        return round(self.completed_task_count() * 100 / total)

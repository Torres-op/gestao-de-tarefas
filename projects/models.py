from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Project(models.Model):
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

    def clean(self):
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({"due_date": "O prazo final não pode ser anterior à data de início."})

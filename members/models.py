from django.db import models
from django.urls import reverse

from core.models import OrganizationOwned


class Member(OrganizationOwned):
    name = models.CharField("Nome", max_length=120)
    email = models.EmailField("E-mail")
    role = models.CharField("Função", max_length=80, blank=True)
    is_active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField("Cadastrado em", auto_now_add=True)

    class Meta:
        verbose_name = "Membro"
        verbose_name_plural = "Membros"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="unique_member_email_per_organization",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("members:detail", kwargs={"pk": self.pk})

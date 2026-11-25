from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField("Nome", max_length=120, unique=True)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationOwned(models.Model):
    organization = models.ForeignKey(
        Organization,
        verbose_name="Organização",
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        OPERATOR = "operator", "Operador"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="profile",
    )
    organization = models.ForeignKey(
        Organization,
        verbose_name="Organização",
        on_delete=models.PROTECT,
        related_name="profiles",
    )
    role = models.CharField("Papel", max_length=20, choices=Role.choices, default=Role.OPERATOR)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"
        ordering = ["organization__name", "user__username"]

    def __str__(self):
        return f"{self.user} ({self.get_role_display()} · {self.organization})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

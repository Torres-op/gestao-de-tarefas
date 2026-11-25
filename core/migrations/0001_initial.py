import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Nome")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criada em")),
            ],
            options={
                "verbose_name": "Organização",
                "verbose_name_plural": "Organizações",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("admin", "Administrador"), ("operator", "Operador")],
                        default="operator",
                        max_length=20,
                        verbose_name="Papel",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="profiles",
                        to="core.organization",
                        verbose_name="Organização",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Perfil",
                "verbose_name_plural": "Perfis",
                "ordering": ["organization__name", "user__username"],
            },
        ),
    ]

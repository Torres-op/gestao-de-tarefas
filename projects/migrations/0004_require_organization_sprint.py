import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("projects", "0003_default_organization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="core.organization",
                verbose_name="Organização",
            ),
        ),
        migrations.CreateModel(
            name="Sprint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, verbose_name="Nome")),
                ("goal", models.TextField(blank=True, verbose_name="Objetivo")),
                ("start_date", models.DateField(verbose_name="Início")),
                ("end_date", models.DateField(verbose_name="Fim")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criada em")),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sprints",
                        to="projects.project",
                        verbose_name="Projeto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sprint",
                "verbose_name_plural": "Sprints",
                "ordering": ["project__name", "start_date"],
                "constraints": [
                    models.UniqueConstraint(fields=("project", "name"), name="unique_sprint_name_per_project"),
                    models.CheckConstraint(
                        condition=models.Q(("end_date__gte", models.F("start_date"))),
                        name="sprint_end_after_start",
                    ),
                ],
            },
        ),
    ]

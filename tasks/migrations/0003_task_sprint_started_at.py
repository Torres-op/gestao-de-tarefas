import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def fill_started_at(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Task.objects.exclude(status="pending").filter(started_at__isnull=True).update(started_at=F("created_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0004_require_organization_sprint"),
        ("tasks", "0002_taskdependency"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="sprint",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tasks",
                to="projects.sprint",
                verbose_name="Sprint",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Iniciada em"),
        ),
        migrations.RunPython(fill_started_at, migrations.RunPython.noop),
    ]

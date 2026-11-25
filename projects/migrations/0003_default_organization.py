from django.db import migrations

DEFAULT_ORGANIZATION = "Organização padrão"


def assign_default_organization(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    Project = apps.get_model("projects", "Project")
    orphans = Project.objects.filter(organization__isnull=True)
    if not orphans.exists():
        return
    organization, _ = Organization.objects.get_or_create(name=DEFAULT_ORGANIZATION)
    orphans.update(organization=organization)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_project_organization"),
    ]

    operations = [
        migrations.RunPython(assign_default_organization, migrations.RunPython.noop),
    ]

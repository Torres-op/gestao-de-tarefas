from django.db import migrations

DEFAULT_ORGANIZATION = "Organização padrão"


def assign_default_organization(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    Member = apps.get_model("members", "Member")
    orphans = Member.objects.filter(organization__isnull=True)
    if not orphans.exists():
        return
    organization, _ = Organization.objects.get_or_create(name=DEFAULT_ORGANIZATION)
    orphans.update(organization=organization)


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0002_member_organization"),
    ]

    operations = [
        migrations.RunPython(assign_default_organization, migrations.RunPython.noop),
    ]

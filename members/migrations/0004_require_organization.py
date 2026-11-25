import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("members", "0003_default_organization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="member",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="core.organization",
                verbose_name="Organização",
            ),
        ),
        migrations.AlterField(
            model_name="member",
            name="email",
            field=models.EmailField(max_length=254, verbose_name="E-mail"),
        ),
        migrations.AddConstraint(
            model_name="member",
            constraint=models.UniqueConstraint(
                fields=("organization", "email"),
                name="unique_member_email_per_organization",
            ),
        ),
    ]

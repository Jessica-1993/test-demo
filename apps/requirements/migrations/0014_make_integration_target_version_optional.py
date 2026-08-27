from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0013_requirementconflict_requirementfamily_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requirementintegrationbatch",
            name="target_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="integration_batches", to="requirements.requirementversion", verbose_name="目标版本（兼容保留）"),
        ),
        migrations.AlterField(
            model_name="requirementintegrationrun",
            name="target_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="integration_runs", to="requirements.requirementversion", verbose_name="目标版本（兼容保留）"),
        ),
    ]

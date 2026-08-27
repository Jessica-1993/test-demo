from django.db import migrations, models
from django.utils import timezone


def publish_existing_drafts(apps, schema_editor):
    RequirementVersion = apps.get_model("requirements", "RequirementVersion")
    now = timezone.now()
    for version in RequirementVersion.objects.filter(status="draft").iterator():
        version.status = "published"
        version.published_by_id = version.published_by_id or version.created_by_id
        version.published_at = version.published_at or now
        version.save(update_fields=["status", "published_by", "published_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0014_make_integration_target_version_optional"),
    ]

    operations = [
        migrations.RunPython(publish_existing_drafts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="requirementversion",
            name="status",
            field=models.CharField(
                choices=[("published", "已发布"), ("archived", "归档")],
                default="published",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]

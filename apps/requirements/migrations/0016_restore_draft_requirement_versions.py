from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0015_remove_draft_requirement_versions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requirementversion",
            name="status",
            field=models.CharField(
                choices=[("draft", "待发布"), ("published", "已发布"), ("archived", "归档")],
                default="draft",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]

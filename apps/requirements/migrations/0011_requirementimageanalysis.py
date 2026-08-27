from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0010_requirementitem_confirmation"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequirementImageAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "待分析"), ("completed", "已完成"), ("failed", "失败")],
                        default="pending",
                        max_length=20,
                        verbose_name="状态",
                    ),
                ),
                ("model_name", models.CharField(blank=True, max_length=120, verbose_name="分析模型")),
                ("summary", models.JSONField(blank=True, default=dict, verbose_name="结构化摘要")),
                ("raw_response", models.JSONField(blank=True, default=dict, verbose_name="模型原始响应")),
                ("error_message", models.TextField(blank=True, verbose_name="错误信息")),
                ("analyzed_at", models.DateTimeField(blank=True, null=True, verbose_name="分析时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "content_block",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_analysis",
                        to="requirements.requirementcontentblock",
                        verbose_name="图片内容块",
                    ),
                ),
            ],
            options={
                "verbose_name": "需求图片理解结果",
                "verbose_name_plural": "需求图片理解结果",
                "db_table": "requirement_image_analyses",
            },
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("requirements", "0011_requirementimageanalysis"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequirementIntegrationDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "待整合"), ("completed", "已完成"), ("failed", "失败")], default="pending", max_length=20, verbose_name="状态")),
                ("title", models.CharField(blank=True, max_length=200, verbose_name="整合标题")),
                ("module", models.CharField(blank=True, max_length=100, verbose_name="整合模块")),
                ("description", models.TextField(blank=True, verbose_name="整合描述")),
                ("acceptance_criteria", models.TextField(blank=True, verbose_name="整合验收标准")),
                ("supplementary_description", models.TextField(blank=True, verbose_name="整合补充描述")),
                ("source_summary", models.TextField(blank=True, verbose_name="来源摘要")),
                ("raw_context", models.TextField(blank=True, verbose_name="原始上下文")),
                ("model_name", models.CharField(blank=True, max_length=120, verbose_name="模型名称")),
                ("prompt_name", models.CharField(blank=True, max_length=120, verbose_name="提示词名称")),
                ("error_message", models.TextField(blank=True, verbose_name="错误信息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_requirement_integration_drafts", to=settings.AUTH_USER_MODEL, verbose_name="创建人")),
                ("requirement_item", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="integration_draft", to="requirements.requirementitem", verbose_name="详细需求")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="updated_requirement_integration_drafts", to=settings.AUTH_USER_MODEL, verbose_name="更新人")),
            ],
            options={
                "verbose_name": "需求整合稿",
                "verbose_name_plural": "需求整合稿",
                "db_table": "requirement_integration_drafts",
                "ordering": ["-updated_at"],
            },
        ),
    ]

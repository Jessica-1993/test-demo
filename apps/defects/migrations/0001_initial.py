from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("configuration", "0011_testcase_enhancer_role"),
        ("project_knowledge", "0002_projectmodulerevision_and_more"),
        ("requirements", "0019_testcase_enhancement"),
    ]
    operations = [
        migrations.CreateModel(
            name="DefectImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filename", models.CharField(max_length=255, verbose_name="文件名")),
                ("status", models.CharField(choices=[("processing", "处理中"), ("completed", "已完成"), ("partial_success", "部分成功"), ("failed", "失败")], default="processing", max_length=24, verbose_name="状态")),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("errors", models.JSONField(blank=True, default=list, verbose_name="错误明细")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="defect_import_batches", to=settings.AUTH_USER_MODEL, verbose_name="导入人")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="defect_import_batches", to="configuration.projectconfig", verbose_name="项目")),
            ],
            options={"db_table": "defect_import_batches", "ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="Defect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("defect_no", models.CharField(max_length=80, verbose_name="缺陷编号")),
                ("title", models.CharField(max_length=300, verbose_name="缺陷标题")),
                ("description", models.TextField(blank=True, verbose_name="缺陷描述")),
                ("reproduction_steps", models.TextField(blank=True, verbose_name="复现步骤")),
                ("actual_result", models.TextField(blank=True, verbose_name="实际结果")),
                ("expected_result", models.TextField(blank=True, verbose_name="预期结果")),
                ("root_cause", models.TextField(blank=True, verbose_name="根因")),
                ("resolution", models.TextField(blank=True, verbose_name="解决方案")),
                ("severity", models.CharField(choices=[("critical", "致命"), ("high", "严重"), ("medium", "一般"), ("low", "轻微")], default="medium", max_length=20, verbose_name="严重程度")),
                ("lifecycle_status", models.CharField(choices=[("open", "待处理"), ("resolved", "已解决"), ("closed", "已关闭"), ("rejected", "已拒绝")], default="open", max_length=20, verbose_name="生命周期状态")),
                ("knowledge_status", models.CharField(choices=[("draft", "待确认"), ("confirmed", "已确认"), ("invalid", "已作废")], default="draft", max_length=20, verbose_name="知识确认状态")),
                ("tags", models.JSONField(blank=True, default=list, verbose_name="标签")),
                ("external_source", models.CharField(blank=True, max_length=80, verbose_name="外部来源")),
                ("external_id", models.CharField(blank=True, max_length=160, verbose_name="外部编号")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="确认时间")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_defects", to=settings.AUTH_USER_MODEL, verbose_name="确认人")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_defects", to=settings.AUTH_USER_MODEL, verbose_name="创建人")),
                ("detected_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="detected_defects", to="requirements.requirementversion", verbose_name="发现版本")),
                ("fixed_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fixed_defects", to="requirements.requirementversion", verbose_name="修复版本")),
                ("modules", models.ManyToManyField(blank=True, related_name="defects", to="project_knowledge.projectmodule", verbose_name="正式模块")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="defects", to="configuration.projectconfig", verbose_name="项目")),
                ("requirement_revisions", models.ManyToManyField(blank=True, related_name="defects", to="requirements.requirementrevision", verbose_name="正式需求修订")),
                ("test_cases", models.ManyToManyField(blank=True, related_name="defects", to="requirements.testcase", verbose_name="关联用例")),
            ],
            options={"db_table": "defects", "ordering": ["-updated_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="defect", constraint=models.UniqueConstraint(fields=("project", "defect_no"), name="uniq_project_defect_no")),
        migrations.AddIndex(model_name="defect", index=models.Index(fields=["project", "knowledge_status", "severity"], name="defect_project_status_idx")),
    ]

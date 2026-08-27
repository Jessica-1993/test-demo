from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_testcase_revisions(apps, schema_editor):
    TestCase = apps.get_model("requirements", "TestCase")
    for case in TestCase.objects.filter(requirement_revision__isnull=True).iterator():
        revision_ids = list(
            case.version.requirement_revisions.filter(source_item_id=case.requirement_item_id)
            .values_list("id", flat=True)[:2]
        )
        if len(revision_ids) == 1:
            case.requirement_revision_id = revision_ids[0]
            case.save(update_fields=["requirement_revision"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("requirements", "0018_remove_single_module_relations"),
    ]
    operations = [
        migrations.CreateModel(
            name="TestCaseEnhancementTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_no", models.CharField(max_length=60, unique=True, verbose_name="任务编号")),
                ("status", models.CharField(choices=[("pending", "等待中"), ("running", "增强中"), ("completed", "已完成"), ("partial_success", "部分成功"), ("failed", "失败")], default="pending", max_length=24, verbose_name="状态")),
                ("progress", models.PositiveIntegerField(default=0, verbose_name="进度")),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("enhancer_model", models.CharField(blank=True, max_length=120, verbose_name="增强模型")),
                ("reviewer_model", models.CharField(blank=True, max_length=120, verbose_name="评审模型")),
                ("retrieval_snapshot", models.JSONField(blank=True, default=dict, verbose_name="检索摘要")),
                ("task_log", models.JSONField(blank=True, default=list, verbose_name="任务日志")),
                ("error_message", models.TextField(blank=True, verbose_name="错误信息")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_testcase_enhancement_tasks", to=settings.AUTH_USER_MODEL, verbose_name="创建人")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="testcase_enhancement_tasks", to="configuration.projectconfig", verbose_name="项目")),
                ("requirement_revisions", models.ManyToManyField(related_name="enhancement_tasks", to="requirements.requirementrevision", verbose_name="正式需求修订")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enhancement_tasks", to="requirements.requirementversion", verbose_name="目标版本")),
            ],
            options={"db_table": "testcase_enhancement_tasks", "ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="TestCaseEnhancementEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("usage", models.CharField(choices=[("historical_case", "历史用例"), ("defect", "历史缺陷")], max_length=24, verbose_name="用途")),
                ("asset_type", models.CharField(max_length=40)),
                ("asset_id", models.PositiveBigIntegerField()),
                ("rank", models.PositiveIntegerField()),
                ("identifier", models.CharField(blank=True, max_length=120)),
                ("title", models.CharField(blank=True, max_length=300)),
                ("excerpt", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("requirement_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enhancement_evidence", to="requirements.requirementrevision", verbose_name="正式需求修订")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence", to="requirements.testcaseenhancementtask", verbose_name="增强任务")),
            ],
            options={"db_table": "testcase_enhancement_evidence", "ordering": ["requirement_revision", "rank", "id"]},
        ),
        migrations.AddConstraint(
            model_name="testcaseenhancementevidence",
            constraint=models.UniqueConstraint(fields=("task", "requirement_revision", "asset_type", "asset_id"), name="uniq_enhancement_evidence_asset"),
        ),
        migrations.CreateModel(
            name="TestCaseEnhancementSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("add", "新增用例"), ("update", "优化用例")], max_length=12)),
                ("before_hash", models.CharField(blank=True, max_length=64)),
                ("before_snapshot", models.JSONField(blank=True, default=dict)),
                ("proposed_content", models.JSONField(default=dict)),
                ("rationale", models.TextField()),
                ("evidence_basis", models.CharField(default="evidence", max_length=24, verbose_name="依据类型")),
                ("review_passed", models.BooleanField(default=False)),
                ("review_feedback", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "待确认"), ("accepted", "已接受"), ("rejected", "已拒绝"), ("conflict", "内容冲突")], default="pending", max_length=20)),
                ("decision_note", models.TextField(blank=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("applied_case", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="applied_enhancement_suggestions", to="requirements.testcase", verbose_name="落库用例")),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="decided_testcase_enhancement_suggestions", to=settings.AUTH_USER_MODEL)),
                ("evidence", models.ManyToManyField(blank=True, related_name="suggestions", to="requirements.testcaseenhancementevidence", verbose_name="引用证据")),
                ("requirement_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enhancement_suggestions", to="requirements.requirementrevision", verbose_name="正式需求修订")),
                ("target_case", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="enhancement_suggestions", to="requirements.testcase", verbose_name="目标用例")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="suggestions", to="requirements.testcaseenhancementtask", verbose_name="增强任务")),
            ],
            options={"db_table": "testcase_enhancement_suggestions", "ordering": ["requirement_revision", "id"]},
        ),
        migrations.AddIndex(
            model_name="testcaseenhancementsuggestion",
            index=models.Index(fields=["task", "status"], name="enhancement_task_status_idx"),
        ),
        migrations.RunPython(backfill_testcase_revisions, migrations.RunPython.noop),
    ]

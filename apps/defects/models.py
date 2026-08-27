from django.conf import settings
from django.db import models

from apps.configuration.models import ProjectConfig


class Defect(models.Model):
    SEVERITY_CHOICES = [
        ("critical", "致命"),
        ("high", "严重"),
        ("medium", "一般"),
        ("low", "轻微"),
    ]
    LIFECYCLE_CHOICES = [
        ("open", "待处理"),
        ("resolved", "已解决"),
        ("closed", "已关闭"),
        ("rejected", "已拒绝"),
    ]
    KNOWLEDGE_STATUS_CHOICES = [
        ("draft", "待确认"),
        ("confirmed", "已确认"),
        ("invalid", "已作废"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="defects", verbose_name="项目")
    defect_no = models.CharField(max_length=80, verbose_name="缺陷编号")
    title = models.CharField(max_length=300, verbose_name="缺陷标题")
    description = models.TextField(blank=True, verbose_name="缺陷描述")
    reproduction_steps = models.TextField(blank=True, verbose_name="复现步骤")
    actual_result = models.TextField(blank=True, verbose_name="实际结果")
    expected_result = models.TextField(blank=True, verbose_name="预期结果")
    root_cause = models.TextField(blank=True, verbose_name="根因")
    resolution = models.TextField(blank=True, verbose_name="解决方案")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium", verbose_name="严重程度")
    lifecycle_status = models.CharField(max_length=20, choices=LIFECYCLE_CHOICES, default="open", verbose_name="生命周期状态")
    knowledge_status = models.CharField(max_length=20, choices=KNOWLEDGE_STATUS_CHOICES, default="draft", verbose_name="知识确认状态")
    detected_version = models.ForeignKey("requirements.RequirementVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="detected_defects", verbose_name="发现版本")
    fixed_version = models.ForeignKey("requirements.RequirementVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="fixed_defects", verbose_name="修复版本")
    modules = models.ManyToManyField("project_knowledge.ProjectModule", blank=True, related_name="defects", verbose_name="正式模块")
    requirement_revisions = models.ManyToManyField("requirements.RequirementRevision", blank=True, related_name="defects", verbose_name="正式需求修订")
    test_cases = models.ManyToManyField("requirements.TestCase", blank=True, related_name="defects", verbose_name="关联用例")
    tags = models.JSONField(default=list, blank=True, verbose_name="标签")
    external_source = models.CharField(max_length=80, blank=True, verbose_name="外部来源")
    external_id = models.CharField(max_length=160, blank=True, verbose_name="外部编号")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_defects", verbose_name="创建人")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_defects", verbose_name="确认人")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "defects"
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["project", "defect_no"], name="uniq_project_defect_no")]
        indexes = [
            models.Index(fields=["project", "knowledge_status", "severity"], name="defect_project_status_idx"),
        ]

    def __str__(self):
        return f"{self.defect_no} {self.title}"


class DefectImportBatch(models.Model):
    STATUS_CHOICES = [
        ("processing", "处理中"),
        ("completed", "已完成"),
        ("partial_success", "部分成功"),
        ("failed", "失败"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="defect_import_batches", verbose_name="项目")
    filename = models.CharField(max_length=255, verbose_name="文件名")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="processing", verbose_name="状态")
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True, verbose_name="错误明细")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="defect_import_batches", verbose_name="导入人")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "defect_import_batches"
        ordering = ["-created_at", "-id"]

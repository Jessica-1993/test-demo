from django.conf import settings
from django.db import models

from apps.configuration.models import ProjectConfig


class ProjectModule(models.Model):
    STATUS_CHOICES = [("active", "启用"), ("inactive", "停用")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="formal_modules", verbose_name="项目")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", verbose_name="上级模块")
    code = models.SlugField(max_length=80, verbose_name="模块编码")
    name = models.CharField(max_length=120, verbose_name="模块名称")
    description = models.TextField(blank=True, verbose_name="模块说明")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_modules"
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["project", "code"], name="uniq_project_module_code")]

    def __str__(self):
        return f"{self.project.code}/{self.code}"

    @property
    def path(self):
        names = []
        current = self
        visited = set()
        while current and current.pk not in visited:
            visited.add(current.pk)
            names.append(current.name)
            current = current.parent
        return " / ".join(reversed(names))


class ProjectModuleRevision(models.Model):
    STATUS_CHOICES = [
        ("candidate", "待确认"),
        ("confirmed", "已确认"),
        ("superseded", "已替代"),
    ]

    module = models.ForeignKey(ProjectModule, on_delete=models.CASCADE, related_name="revisions", verbose_name="模块")
    revision_no = models.PositiveIntegerField(verbose_name="修订号")
    parent = models.ForeignKey(ProjectModule, on_delete=models.PROTECT, null=True, blank=True, related_name="pending_child_revisions", verbose_name="上级模块")
    code = models.SlugField(max_length=80, verbose_name="模块编码")
    name = models.CharField(max_length=120, verbose_name="模块名称")
    description = models.TextField(blank=True, verbose_name="模块说明")
    module_status = models.CharField(max_length=20, choices=ProjectModule.STATUS_CHOICES, default="active", verbose_name="模块状态")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="candidate", verbose_name="修订状态")
    previous_revision = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="next_revisions", verbose_name="前一修订")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_project_module_revisions", verbose_name="创建人")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_project_module_revisions", verbose_name="确认人")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "project_module_revisions"
        ordering = ["-revision_no", "-id"]
        constraints = [models.UniqueConstraint(fields=["module", "revision_no"], name="uniq_project_module_revision_no")]


class ProjectModuleAlias(models.Model):
    module = models.ForeignKey(ProjectModule, on_delete=models.CASCADE, related_name="aliases", verbose_name="模块")
    alias = models.CharField(max_length=120, verbose_name="别名")
    normalized_alias = models.CharField(max_length=120, verbose_name="归一化别名")

    class Meta:
        db_table = "project_module_aliases"
        constraints = [models.UniqueConstraint(fields=["module", "normalized_alias"], name="uniq_module_normalized_alias")]


class ProjectKnowledgeItem(models.Model):
    CATEGORY_CHOICES = [
        ("term", "术语"),
        ("role_permission", "角色权限"),
        ("module_boundary", "模块边界"),
        ("business_rule", "业务规则"),
        ("business_flow", "业务流程"),
        ("non_functional", "非功能约束"),
        ("external_dependency", "外部依赖"),
    ]
    STATUS_CHOICES = [("active", "有效"), ("retired", "已失效")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="knowledge_items", verbose_name="项目")
    module = models.ForeignKey(ProjectModule, on_delete=models.PROTECT, null=True, blank=True, related_name="knowledge_items", verbose_name="适用模块")
    code = models.CharField(max_length=80, verbose_name="知识编码")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, verbose_name="知识类别")
    title = models.CharField(max_length=200, verbose_name="知识标题")
    tags = models.JSONField(default=list, blank=True, verbose_name="标签")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_knowledge_items"
        ordering = ["category", "code"]
        constraints = [models.UniqueConstraint(fields=["project", "code"], name="uniq_project_knowledge_code")]


class ProjectKnowledgeRevision(models.Model):
    STATUS_CHOICES = [
        ("candidate", "待确认"),
        ("conflict", "有冲突"),
        ("confirmed", "已确认"),
        ("superseded", "已替代"),
        ("retired", "已失效"),
        ("rejected", "已拒绝"),
    ]

    item = models.ForeignKey(ProjectKnowledgeItem, on_delete=models.CASCADE, related_name="revisions", verbose_name="知识项")
    revision_no = models.PositiveIntegerField(verbose_name="修订号")
    title = models.CharField(max_length=200, verbose_name="标题快照")
    content = models.TextField(verbose_name="知识内容")
    effective_from_version = models.ForeignKey("requirements.RequirementVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="effective_knowledge_revisions", verbose_name="生效版本")
    previous_revision = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="next_revisions", verbose_name="前一修订")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="candidate", verbose_name="状态")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="提取模型")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_knowledge_revisions", verbose_name="创建人")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_knowledge_revisions", verbose_name="确认人")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_knowledge_revisions"
        ordering = ["-revision_no", "-id"]
        constraints = [models.UniqueConstraint(fields=["item", "revision_no"], name="uniq_knowledge_revision_no")]


class ProjectKnowledgeEvidence(models.Model):
    revision = models.ForeignKey(ProjectKnowledgeRevision, on_delete=models.CASCADE, related_name="evidence", verbose_name="知识修订")
    source_type = models.CharField(max_length=40, verbose_name="来源类型")
    source_id = models.PositiveBigIntegerField(verbose_name="来源ID")
    source_revision_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="来源修订ID")
    source_locator = models.CharField(max_length=255, blank=True, verbose_name="来源位置")
    excerpt = models.TextField(verbose_name="证据快照")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_knowledge_evidence"


class KnowledgeExtractionRun(models.Model):
    STATUS_CHOICES = [("pending", "等待中"), ("running", "执行中"), ("completed", "已完成"), ("partial_success", "部分成功"), ("failed", "失败")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="knowledge_extraction_runs", verbose_name="项目")
    source_document_ids = models.JSONField(default=list, blank=True, verbose_name="来源文档ID")
    include_confirmed_requirements = models.BooleanField(default=True, verbose_name="包含已确认需求")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    candidate_count = models.PositiveIntegerField(default=0, verbose_name="候选数")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="模型")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="knowledge_extraction_runs", verbose_name="执行人")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_extraction_runs"
        ordering = ["-created_at", "-id"]

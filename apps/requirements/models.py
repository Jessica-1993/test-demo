from django.conf import settings
from django.db import models

from apps.configuration.models import ProjectConfig


class RequirementDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("docx", "Word"),
        ("txt", "文本"),
        ("md", "Markdown"),
        ("other", "其他"),
    ]
    STATUS_CHOICES = [
        ("uploaded", "已上传"),
        ("parsed", "已解析"),
        ("failed", "解析失败"),
        ("archived", "已归档"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="requirement_documents", verbose_name="项目")
    target_version = models.ForeignKey("RequirementVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="source_documents", verbose_name="目标版本")
    title = models.CharField(max_length=200, verbose_name="文档标题")
    original_filename = models.CharField(max_length=255, verbose_name="原始文件名")
    document_type = models.CharField(max_length=12, choices=DOCUMENT_TYPE_CHOICES, default="other", verbose_name="文档类型")
    file_size = models.PositiveIntegerField(default=0, verbose_name="文件大小")
    qiniu_key = models.CharField(max_length=255, unique=True, verbose_name="七牛对象 Key")
    qiniu_url = models.URLField(max_length=1000, blank=True, verbose_name="七牛访问地址")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded", verbose_name="状态")
    parse_message = models.TextField(blank=True, verbose_name="解析信息")
    extracted_text = models.TextField(blank=True, verbose_name="提取文本")
    extracted_blocks = models.JSONField(default=list, blank=True, verbose_name="结构化内容块")
    extraction_engine = models.CharField(max_length=40, blank=True, verbose_name="解析引擎")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requirement_documents", verbose_name="上传人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "requirement_documents"
        verbose_name = "需求文档"
        verbose_name_plural = "需求文档"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class RequirementParseRun(models.Model):
    STATUS_CHOICES = [
        ("processing", "解析中"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    document = models.ForeignKey(RequirementDocument, on_delete=models.CASCADE, related_name="parse_runs", verbose_name="来源文档")
    run_no = models.PositiveIntegerField(verbose_name="解析批次")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="processing", verbose_name="状态")
    extraction_engine = models.CharField(max_length=40, blank=True, verbose_name="解析引擎")
    message = models.TextField(blank=True, verbose_name="解析信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    block_count = models.PositiveIntegerField(default=0, verbose_name="内容块数")
    requirement_count = models.PositiveIntegerField(default=0, verbose_name="需求数")
    table_count = models.PositiveIntegerField(default=0, verbose_name="表格数")
    image_count = models.PositiveIntegerField(default=0, verbose_name="图片数")
    filtered_count = models.PositiveIntegerField(default=0, verbose_name="过滤块数")
    filtered_blocks = models.JSONField(default=list, blank=True, verbose_name="过滤记录")
    is_current = models.BooleanField(default=False, verbose_name="当前批次")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requirement_parse_runs", verbose_name="执行人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        db_table = "requirement_parse_runs"
        ordering = ["-run_no", "-id"]
        constraints = [models.UniqueConstraint(fields=["document", "run_no"], name="uniq_document_parse_run")]

    def __str__(self):
        return f"{self.document.title} #{self.run_no}"


class RequirementItem(models.Model):
    PRIORITY_CHOICES = [
        ("high", "高"),
        ("medium", "中"),
        ("low", "低"),
    ]
    CONFIRM_STATUS_CHOICES = [
        ("pending", "待确认"),
        ("confirmed", "已确认"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="requirement_items", verbose_name="项目")
    document = models.ForeignKey(RequirementDocument, on_delete=models.CASCADE, related_name="items", verbose_name="来源文档")
    parse_run = models.ForeignKey(RequirementParseRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="items", verbose_name="解析批次")
    requirement_no = models.CharField(max_length=50, verbose_name="需求编号")
    title = models.CharField(max_length=200, verbose_name="需求标题")
    module = models.CharField(max_length=100, verbose_name="功能模块")
    source_module_labels = models.JSONField(default=list, blank=True, verbose_name="原始模块标签")
    formal_modules = models.ManyToManyField("project_knowledge.ProjectModule", blank=True, related_name="requirement_items", verbose_name="正式模块")
    description = models.TextField(verbose_name="需求描述")
    supplementary_description = models.TextField(blank=True, verbose_name="补充描述")
    acceptance_criteria = models.TextField(blank=True, verbose_name="验收标准")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium", verbose_name="优先级")
    confirm_status = models.CharField(max_length=20, choices=CONFIRM_STATUS_CHOICES, default="pending", verbose_name="确认状态")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_requirement_items", verbose_name="确认人")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")
    is_current = models.BooleanField(default=True, verbose_name="当前有效")
    is_archived = models.BooleanField(default=False, verbose_name="已归档")
    merged_from = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="merged_into", verbose_name="合并来源")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "requirement_items"
        verbose_name = "详细需求"
        verbose_name_plural = "详细需求"
        ordering = ["module", "requirement_no"]
        constraints = [models.UniqueConstraint(fields=["document", "parse_run", "requirement_no"], name="uniq_parse_run_requirement_no")]

    def __str__(self):
        return f"{self.requirement_no} {self.title}"


class RequirementContentBlock(models.Model):
    BLOCK_TYPE_CHOICES = [
        ("text", "文本"),
        ("table", "表格"),
        ("image", "图片"),
    ]

    parse_run = models.ForeignKey(RequirementParseRun, on_delete=models.CASCADE, related_name="content_blocks", verbose_name="解析批次")
    requirement = models.ForeignKey(RequirementItem, on_delete=models.CASCADE, null=True, blank=True, related_name="content_blocks", verbose_name="所属需求")
    block_type = models.CharField(max_length=12, choices=BLOCK_TYPE_CHOICES, verbose_name="内容类型")
    order = models.PositiveIntegerField(default=0, verbose_name="顺序")
    text = models.TextField(blank=True, verbose_name="文本内容")
    heading_level = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="标题层级")
    page = models.PositiveIntegerField(null=True, blank=True, verbose_name="页码")
    source_locator = models.CharField(max_length=255, blank=True, verbose_name="来源位置")
    table_data = models.JSONField(default=dict, blank=True, verbose_name="表格结构")
    image_key = models.CharField(max_length=500, blank=True, verbose_name="图片对象 Key")
    image_url = models.URLField(max_length=1000, blank=True, verbose_name="图片地址")
    image_width = models.PositiveIntegerField(null=True, blank=True, verbose_name="图片宽度")
    image_height = models.PositiveIntegerField(null=True, blank=True, verbose_name="图片高度")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "requirement_content_blocks"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.parse_run_id} {self.block_type} #{self.order}"


class RequirementIntegrationDraft(models.Model):
    STATUS_CHOICES = [
        ("pending", "待整合"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    requirement_item = models.OneToOneField(
        RequirementItem,
        on_delete=models.CASCADE,
        related_name="integration_draft",
        verbose_name="详细需求",
    )
    target_version = models.ForeignKey("RequirementVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="integration_drafts", verbose_name="目标版本")
    formal_modules = models.ManyToManyField("project_knowledge.ProjectModule", blank=True, related_name="integration_drafts", verbose_name="正式模块")
    suggested_module_paths = models.JSONField(default=list, blank=True, verbose_name="建议模块路径")
    unresolved_module_paths = models.JSONField(default=list, blank=True, verbose_name="未解决模块路径")
    module_resolution_status = models.CharField(
        max_length=20,
        choices=[("resolved", "已解决"), ("needs_review", "待人工处理")],
        default="needs_review",
        verbose_name="模块归属状态",
    )
    selected_family = models.ForeignKey("RequirementFamily", on_delete=models.PROTECT, null=True, blank=True, related_name="selected_drafts", verbose_name="选定需求族")
    relationship_mode = models.CharField(max_length=20, blank=True, verbose_name="关系模式")
    change_type = models.CharField(max_length=20, blank=True, verbose_name="变更类型")
    relationship_confirmed = models.BooleanField(default=False, verbose_name="关系已确认")
    review_status = models.CharField(max_length=20, default="pending", verbose_name="审核状态")
    source_content_hash = models.CharField(max_length=64, blank=True, verbose_name="原文哈希")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_requirement_integration_drafts", verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    title = models.CharField(max_length=200, blank=True, verbose_name="整合标题")
    module = models.CharField(max_length=100, blank=True, verbose_name="整合模块")
    description = models.TextField(blank=True, verbose_name="整合描述")
    acceptance_criteria = models.TextField(blank=True, verbose_name="整合验收标准")
    supplementary_description = models.TextField(blank=True, verbose_name="整合补充描述")
    source_summary = models.TextField(blank=True, verbose_name="来源摘要")
    raw_context = models.TextField(blank=True, verbose_name="原始上下文")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="模型名称")
    prompt_name = models.CharField(max_length=120, blank=True, verbose_name="提示词名称")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_requirement_integration_drafts", verbose_name="创建人")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_requirement_integration_drafts", verbose_name="更新人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "requirement_integration_drafts"
        verbose_name = "需求整合稿"
        verbose_name_plural = "需求整合稿"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.requirement_item_id} {self.status}"


class RequirementImageAnalysis(models.Model):
    STATUS_CHOICES = [
        ("pending", "待分析"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    content_block = models.OneToOneField(
        RequirementContentBlock,
        on_delete=models.CASCADE,
        related_name="image_analysis",
        verbose_name="图片内容块",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="分析模型")
    summary = models.JSONField(default=dict, blank=True, verbose_name="结构化摘要")
    raw_response = models.JSONField(default=dict, blank=True, verbose_name="模型原始响应")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    analyzed_at = models.DateTimeField(null=True, blank=True, verbose_name="分析时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "requirement_image_analyses"
        verbose_name = "需求图片理解结果"
        verbose_name_plural = "需求图片理解结果"

    def __str__(self):
        return f"{self.content_block_id} {self.status}"


class RequirementVersion(models.Model):
    STATUS_CHOICES = [
        ("draft", "待发布"),
        ("published", "已发布"),
        ("archived", "归档"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="requirement_versions", verbose_name="项目")
    name = models.CharField(max_length=120, verbose_name="版本名称")
    version_no = models.CharField(max_length=80, verbose_name="版本号")
    sequence = models.PositiveIntegerField(default=1, verbose_name="版本顺序")
    description = models.TextField(blank=True, verbose_name="版本描述")
    requirement_items = models.ManyToManyField(RequirementItem, blank=True, related_name="versions", verbose_name="关联详细需求")
    requirement_revisions = models.ManyToManyField("RequirementRevision", blank=True, related_name="versions", verbose_name="正式需求修订")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requirement_versions", verbose_name="创建人")
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="published_requirement_versions", verbose_name="发布人")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="发布时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "requirement_versions"
        verbose_name = "需求版本"
        verbose_name_plural = "需求版本"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "version_no"], name="uniq_project_version_no"),
            models.UniqueConstraint(fields=["project", "sequence"], name="uniq_project_version_sequence"),
        ]

    def __str__(self):
        return f"{self.version_no} {self.name}"

    def save(self, *args, **kwargs):
        if self._state.adding and self.project_id:
            occupied = RequirementVersion.objects.filter(project_id=self.project_id, sequence=self.sequence).exists()
            if occupied:
                from django.db.models import Max
                self.sequence = (RequirementVersion.objects.filter(project_id=self.project_id).aggregate(value=Max("sequence"))["value"] or 0) + 1
        super().save(*args, **kwargs)


class RequirementFamily(models.Model):
    STATUS_CHOICES = [("active", "有效"), ("deprecated", "已废弃")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="requirement_families", verbose_name="项目")
    modules = models.ManyToManyField("project_knowledge.ProjectModule", related_name="requirement_families", verbose_name="正式模块")
    family_no = models.CharField(max_length=80, verbose_name="需求族编号")
    title = models.CharField(max_length=200, verbose_name="需求族标题")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_requirement_families", verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "requirement_families"
        ordering = ["family_no"]
        constraints = [models.UniqueConstraint(fields=["project", "family_no"], name="uniq_project_family_no")]


class RequirementRevision(models.Model):
    CHANGE_TYPE_CHOICES = [
        ("initial", "新增"),
        ("continued", "延续"),
        ("modified", "修改"),
        ("deprecated", "废弃"),
    ]

    family = models.ForeignKey(RequirementFamily, on_delete=models.PROTECT, related_name="revisions", verbose_name="需求族")
    source_item = models.OneToOneField(RequirementItem, on_delete=models.PROTECT, related_name="formal_revision", verbose_name="来源候选需求")
    previous_revision = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="next_revisions", verbose_name="前一修订")
    revision_no = models.PositiveIntegerField(verbose_name="修订号")
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, verbose_name="变更类型")
    title = models.CharField(max_length=200, verbose_name="标题")
    modules = models.ManyToManyField("project_knowledge.ProjectModule", related_name="requirement_revisions", verbose_name="正式模块")
    description = models.TextField(verbose_name="需求描述")
    acceptance_criteria = models.TextField(blank=True, verbose_name="验收标准")
    supplementary_description = models.TextField(blank=True, verbose_name="补充描述")
    source_summary = models.TextField(blank=True, verbose_name="来源摘要")
    source_content_hash = models.CharField(max_length=64, verbose_name="原文哈希")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="confirmed_requirement_revisions", verbose_name="确认人")
    confirmed_at = models.DateTimeField(auto_now_add=True, verbose_name="确认时间")

    class Meta:
        db_table = "requirement_revisions"
        ordering = ["family", "revision_no"]
        constraints = [models.UniqueConstraint(fields=["family", "revision_no"], name="uniq_family_revision_no")]


class RequirementIntegrationBatch(models.Model):
    STATUS_CHOICES = [("pending", "等待中"), ("running", "执行中"), ("completed", "已完成"), ("partial_success", "部分成功"), ("failed", "失败")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="requirement_integration_batches", verbose_name="项目")
    document = models.ForeignKey(RequirementDocument, on_delete=models.CASCADE, related_name="integration_batches", verbose_name="来源文档")
    target_version = models.ForeignKey(RequirementVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="integration_batches", verbose_name="目标版本（兼容保留）")
    requirement_items = models.ManyToManyField(RequirementItem, related_name="integration_batches", verbose_name="候选需求")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requirement_integration_batches", verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "requirement_integration_batches"
        ordering = ["-created_at", "-id"]


class RequirementIntegrationRun(models.Model):
    STATUS_CHOICES = [("pending", "等待中"), ("running", "执行中"), ("completed", "已完成"), ("failed", "失败")]

    batch = models.ForeignKey(RequirementIntegrationBatch, on_delete=models.CASCADE, null=True, blank=True, related_name="runs", verbose_name="批次")
    requirement_item = models.ForeignKey(RequirementItem, on_delete=models.CASCADE, related_name="integration_runs", verbose_name="候选需求")
    target_version = models.ForeignKey(RequirementVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="integration_runs", verbose_name="目标版本（兼容保留）")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    source_content_hash = models.CharField(max_length=64, verbose_name="原文哈希")
    model_name = models.CharField(max_length=120, blank=True)
    prompt_name = models.CharField(max_length=120, blank=True)
    search_snapshot = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requirement_integration_runs", verbose_name="执行人")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "requirement_integration_runs"
        ordering = ["-created_at", "-id"]


class RequirementMatchCandidate(models.Model):
    run = models.ForeignKey(RequirementIntegrationRun, on_delete=models.CASCADE, related_name="match_candidates", verbose_name="整合运行")
    revision = models.ForeignKey(RequirementRevision, on_delete=models.PROTECT, related_name="match_candidates", verbose_name="候选修订")
    keyword_rank = models.PositiveIntegerField(null=True, blank=True)
    vector_rank = models.PositiveIntegerField(null=True, blank=True)
    rrf_rank = models.PositiveIntegerField(verbose_name="融合排名")
    matched_excerpt = models.TextField(blank=True)
    rationale = models.TextField(blank=True)

    class Meta:
        db_table = "requirement_match_candidates"
        constraints = [models.UniqueConstraint(fields=["run", "revision"], name="uniq_run_match_revision")]


class RequirementIntegrationEvidence(models.Model):
    USAGE_CHOICES = [("fact", "当前事实"), ("inherited", "继承规则"), ("change", "变更"), ("conflict", "冲突"), ("coverage", "覆盖提示")]

    run = models.ForeignKey(RequirementIntegrationRun, on_delete=models.CASCADE, related_name="evidence", verbose_name="整合运行")
    usage = models.CharField(max_length=20, choices=USAGE_CHOICES, verbose_name="用途")
    asset_type = models.CharField(max_length=40, verbose_name="资产类型")
    asset_id = models.PositiveBigIntegerField(verbose_name="资产ID")
    asset_revision_id = models.PositiveBigIntegerField(null=True, blank=True)
    chunk_id = models.CharField(max_length=160, blank=True)
    source_locator = models.CharField(max_length=255, blank=True)
    excerpt = models.TextField(verbose_name="证据快照")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "requirement_integration_evidence"


class RequirementConflict(models.Model):
    STATUS_CHOICES = [("pending", "待处理"), ("resolved", "已解决")]
    RESOLUTION_CHOICES = [("current", "采用当前规则"), ("historical", "保留历史规则"), ("manual", "手工规则")]

    run = models.ForeignKey(RequirementIntegrationRun, on_delete=models.CASCADE, related_name="conflicts", verbose_name="整合运行")
    title = models.CharField(max_length=200)
    current_statement = models.TextField()
    historical_statement = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    resolution = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, blank=True)
    final_statement = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="resolved_requirement_conflicts")
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "requirement_conflicts"


class RequirementOpenQuestion(models.Model):
    STATUS_CHOICES = [("open", "待回答"), ("answered", "已回答"), ("not_applicable", "不适用"), ("accepted_warning", "接受警告")]

    run = models.ForeignKey(RequirementIntegrationRun, on_delete=models.CASCADE, related_name="open_questions", verbose_name="整合运行")
    category = models.CharField(max_length=40, blank=True)
    question = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    answer = models.TextField(blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="handled_requirement_questions")
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "requirement_open_questions"


class TestCaseGenerationTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "生成中"),
        ("completed", "已完成"),
        ("partial_success", "部分成功"),
        ("failed", "失败"),
    ]

    task_no = models.CharField(max_length=50, unique=True, verbose_name="任务编号")
    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="testcase_generation_tasks", verbose_name="项目")
    version = models.ForeignKey(RequirementVersion, on_delete=models.PROTECT, related_name="generation_tasks", verbose_name="需求版本")
    requirement_items = models.ManyToManyField(RequirementItem, related_name="generation_tasks", verbose_name="待生成详细需求")
    requirement_revisions = models.ManyToManyField(RequirementRevision, blank=True, related_name="generation_tasks", verbose_name="待生成正式需求")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    progress = models.PositiveIntegerField(default=0, verbose_name="进度")
    total_count = models.PositiveIntegerField(default=0, verbose_name="需求总数")
    success_count = models.PositiveIntegerField(default=0, verbose_name="成功数")
    failed_count = models.PositiveIntegerField(default=0, verbose_name="失败数")
    generation_log = models.JSONField(default=list, blank=True, verbose_name="生成日志")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="testcase_generation_tasks", verbose_name="创建人")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "testcase_generation_tasks"
        verbose_name = "用例生成任务"
        verbose_name_plural = "用例生成任务"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.task_no


class TestCase(models.Model):
    PRIORITY_CHOICES = [
        ("high", "高"),
        ("medium", "中"),
        ("low", "低"),
    ]
    TYPE_CHOICES = [
        ("functional", "功能测试"),
        ("api", "接口测试"),
        ("ui", "界面测试"),
        ("integration", "集成测试"),
        ("performance", "性能测试"),
        ("security", "安全测试"),
    ]
    STATUS_CHOICES = [
        ("active", "生效"),
        ("draft", "草稿"),
        ("deprecated", "废弃"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="test_cases", verbose_name="项目")
    version = models.ForeignKey(RequirementVersion, on_delete=models.PROTECT, related_name="test_cases", verbose_name="需求版本")
    requirement_item = models.ForeignKey(RequirementItem, on_delete=models.PROTECT, related_name="test_cases", verbose_name="详细需求")
    requirement_revision = models.ForeignKey(RequirementRevision, on_delete=models.PROTECT, null=True, blank=True, related_name="test_cases", verbose_name="正式需求修订")
    generation_task = models.ForeignKey(TestCaseGenerationTask, on_delete=models.SET_NULL, null=True, blank=True, related_name="test_cases", verbose_name="生成任务")
    case_no = models.CharField(max_length=80, verbose_name="用例编号")
    title = models.CharField(max_length=300, verbose_name="用例标题")
    preconditions = models.TextField(blank=True, verbose_name="前置条件")
    steps = models.TextField(verbose_name="操作步骤")
    expected_result = models.TextField(verbose_name="预期结果")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium", verbose_name="优先级")
    test_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="functional", verbose_name="测试类型")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态")
    generated_by_model = models.CharField(max_length=120, blank=True, verbose_name="生成模型")
    reviewed_by_model = models.CharField(max_length=120, blank=True, verbose_name="审核模型")
    review_feedback = models.TextField(blank=True, verbose_name="审核意见")
    raw_content = models.JSONField(default=dict, blank=True, verbose_name="原始内容")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_test_cases", verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "test_cases"
        verbose_name = "测试用例"
        verbose_name_plural = "测试用例"
        ordering = ["-created_at", "-id"]
        unique_together = ["version", "requirement_item", "case_no"]

    def __str__(self):
        return f"{self.case_no} {self.title}"


class TestCaseEnhancementTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "增强中"),
        ("completed", "已完成"),
        ("partial_success", "部分成功"),
        ("failed", "失败"),
    ]

    task_no = models.CharField(max_length=60, unique=True, verbose_name="任务编号")
    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="testcase_enhancement_tasks", verbose_name="项目")
    version = models.ForeignKey(RequirementVersion, on_delete=models.PROTECT, related_name="enhancement_tasks", verbose_name="目标版本")
    requirement_revisions = models.ManyToManyField(RequirementRevision, related_name="enhancement_tasks", verbose_name="正式需求修订")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    progress = models.PositiveIntegerField(default=0, verbose_name="进度")
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    enhancer_model = models.CharField(max_length=120, blank=True, verbose_name="增强模型")
    reviewer_model = models.CharField(max_length=120, blank=True, verbose_name="评审模型")
    retrieval_snapshot = models.JSONField(default=dict, blank=True, verbose_name="检索摘要")
    task_log = models.JSONField(default=list, blank=True, verbose_name="任务日志")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_testcase_enhancement_tasks", verbose_name="创建人")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testcase_enhancement_tasks"
        ordering = ["-created_at", "-id"]


class TestCaseEnhancementEvidence(models.Model):
    USAGE_CHOICES = [
        ("historical_case", "历史用例"),
        ("defect", "历史缺陷"),
    ]

    task = models.ForeignKey(TestCaseEnhancementTask, on_delete=models.CASCADE, related_name="evidence", verbose_name="增强任务")
    requirement_revision = models.ForeignKey(RequirementRevision, on_delete=models.PROTECT, related_name="enhancement_evidence", verbose_name="正式需求修订")
    usage = models.CharField(max_length=24, choices=USAGE_CHOICES, verbose_name="用途")
    asset_type = models.CharField(max_length=40)
    asset_id = models.PositiveBigIntegerField()
    rank = models.PositiveIntegerField()
    identifier = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=300, blank=True)
    excerpt = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testcase_enhancement_evidence"
        ordering = ["requirement_revision", "rank", "id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "requirement_revision", "asset_type", "asset_id"], name="uniq_enhancement_evidence_asset"),
        ]


class TestCaseEnhancementSuggestion(models.Model):
    ACTION_CHOICES = [("add", "新增用例"), ("update", "优化用例")]
    STATUS_CHOICES = [
        ("pending", "待确认"),
        ("accepted", "已接受"),
        ("rejected", "已拒绝"),
        ("conflict", "内容冲突"),
    ]

    task = models.ForeignKey(TestCaseEnhancementTask, on_delete=models.CASCADE, related_name="suggestions", verbose_name="增强任务")
    requirement_revision = models.ForeignKey(RequirementRevision, on_delete=models.PROTECT, related_name="enhancement_suggestions", verbose_name="正式需求修订")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    target_case = models.ForeignKey(TestCase, on_delete=models.PROTECT, null=True, blank=True, related_name="enhancement_suggestions", verbose_name="目标用例")
    before_hash = models.CharField(max_length=64, blank=True)
    before_snapshot = models.JSONField(default=dict, blank=True)
    proposed_content = models.JSONField(default=dict)
    rationale = models.TextField()
    evidence_basis = models.CharField(max_length=24, default="evidence", verbose_name="依据类型")
    evidence = models.ManyToManyField(TestCaseEnhancementEvidence, blank=True, related_name="suggestions", verbose_name="引用证据")
    review_passed = models.BooleanField(default=False)
    review_feedback = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    applied_case = models.ForeignKey(TestCase, on_delete=models.PROTECT, null=True, blank=True, related_name="applied_enhancement_suggestions", verbose_name="落库用例")
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="decided_testcase_enhancement_suggestions")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testcase_enhancement_suggestions"
        ordering = ["requirement_revision", "id"]
        indexes = [models.Index(fields=["task", "status"], name="enhancement_task_status_idx")]

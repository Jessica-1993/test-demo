from django.db.models import Q
from rest_framework import serializers

from apps.configuration.models import ProjectConfig, PromptConfig
from apps.project_knowledge.models import ProjectModule

from .models import (
    RequirementConflict, RequirementContentBlock, RequirementDocument, RequirementFamily,
    RequirementIntegrationBatch, RequirementIntegrationDraft, RequirementIntegrationEvidence, RequirementIntegrationRun,
    RequirementItem, RequirementMatchCandidate, RequirementOpenQuestion, RequirementParseRun,
    RequirementRevision, RequirementVersion, TestCase, TestCaseEnhancementEvidence,
    TestCaseEnhancementSuggestion, TestCaseEnhancementTask, TestCaseGenerationTask,
)
from .services import RequirementParser, TestCaseGenerationError


class RequirementDocumentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.username", read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    current_run = serializers.SerializerMethodField()

    class Meta:
        model = RequirementDocument
        fields = [
            "id", "project", "project_name", "title", "original_filename", "document_type",
            "file_size", "qiniu_key", "qiniu_url", "status", "status_label", "parse_message",
            "extraction_engine", "current_run", "uploaded_by", "uploaded_by_name",
            "items_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "original_filename", "document_type", "file_size", "qiniu_key", "qiniu_url",
            "status", "parse_message", "extraction_engine", "current_run",
            "uploaded_by", "created_at", "updated_at",
        ]

    def get_current_run(self, obj):
        run = next((run for run in getattr(obj, "prefetched_runs", []) if run.is_current), None)
        if not run:
            run = obj.parse_runs.filter(is_current=True).first()
        return RequirementParseRunSerializer(run).data if run else None


class RequirementDocumentUploadSerializer(serializers.Serializer):
    project = serializers.IntegerField()
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    file = serializers.FileField()

    def validate_file(self, file):
        document_type = RequirementParser.detect_type(file.name)
        if document_type == "other":
            raise serializers.ValidationError("仅支持 pdf、docx、txt、md 需求文档")
        if file.size > 20 * 1024 * 1024:
            raise serializers.ValidationError("文档不能超过 20MB")
        return file


class RequirementContentBlockSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    image_analysis = serializers.SerializerMethodField()

    class Meta:
        model = RequirementContentBlock
        fields = [
            "id", "parse_run", "requirement", "block_type", "order", "text",
            "heading_level", "page", "table_data", "image_key",
            "image_url", "image_width", "image_height",
            "image_analysis",
        ]
        read_only_fields = ["parse_run", "image_key", "image_url", "image_width", "image_height"]

    def validate_requirement(self, requirement):
        if self.instance and requirement and requirement.parse_run_id != self.instance.parse_run_id:
            raise serializers.ValidationError("内容块只能分配到同一解析批次的需求")
        return requirement

    def get_image_url(self, obj):
        if not obj.image_key:
            return obj.image_url
        from .services import QiniuStorageService
        return QiniuStorageService().access_url(obj.image_key, obj.image_url)

    def get_image_analysis(self, obj):
        try:
            analysis = obj.image_analysis
        except Exception:
            return None
        return {
            "status": analysis.status,
            "model_name": analysis.model_name,
            "summary": analysis.summary,
            "error_message": analysis.error_message,
            "error_info": analysis.error_info,
            "analyzed_at": analysis.analyzed_at,
        }


class RequirementParseRunSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = RequirementParseRun
        fields = [
            "id", "document", "run_no", "status", "status_label", "extraction_engine",
            "message", "error_info", "retry_of", "block_count", "requirement_count", "table_count", "image_count",
            "filtered_count", "filtered_blocks", "is_current", "created_by_name",
            "created_at", "completed_at",
        ]
        read_only_fields = fields


def serialize_modules(modules):
    return [
        {"id": module.id, "code": module.code, "name": module.name, "path": module.path}
        for module in modules.all()
    ]


class RequirementIntegrationDraftSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.username", read_only=True)
    formal_modules = serializers.SerializerMethodField()
    formal_module_ids = serializers.PrimaryKeyRelatedField(
        source="formal_modules", queryset=ProjectModule.objects.all(), many=True, required=False
    )

    class Meta:
        model = RequirementIntegrationDraft
        fields = [
            "id", "requirement_item", "formal_modules", "formal_module_ids", "selected_family",
            "suggested_module_paths", "unresolved_module_paths", "module_resolution_status",
            "relationship_mode", "change_type", "relationship_confirmed", "review_status",
            "source_content_hash", "reviewed_by", "reviewed_at", "status", "status_label", "title", "module",
            "description", "acceptance_criteria", "supplementary_description",
            "source_summary", "raw_context", "model_name", "prompt_name",
            "error_message", "error_info", "created_by", "created_by_name", "updated_by",
            "updated_by_name", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "requirement_item", "source_content_hash", "reviewed_by", "reviewed_at",
            "status", "status_label", "raw_context",
            "suggested_module_paths", "unresolved_module_paths", "module_resolution_status",
            "model_name", "prompt_name", "error_message", "error_info", "created_by",
            "created_by_name", "updated_by", "updated_by_name", "created_at",
            "updated_at",
        ]

    def get_formal_modules(self, obj):
        return serialize_modules(obj.formal_modules)

    def validate(self, attrs):
        modules = attrs.get("formal_modules")
        if modules is not None:
            project_id = self.instance.requirement_item.project_id
            invalid = [module.id for module in modules if module.project_id != project_id or module.status != "active"]
            if invalid:
                raise serializers.ValidationError({"formal_module_ids": f"模块已停用或不属于当前项目: {invalid}"})
        return attrs

    def update(self, instance, validated_data):
        modules_supplied = "formal_modules" in validated_data
        instance = super().update(instance, validated_data)
        if modules_supplied:
            has_modules = instance.formal_modules.exists()
            instance.unresolved_module_paths = []
            instance.module_resolution_status = "resolved" if has_modules else "needs_review"
            instance.save(update_fields=["unresolved_module_paths", "module_resolution_status", "updated_at"])
        return instance


class RequirementItemSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    document_title = serializers.CharField(source="document.title", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    confirm_status_label = serializers.CharField(source="get_confirm_status_display", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)
    content_blocks = RequirementContentBlockSerializer(many=True, read_only=True)
    integration_draft = RequirementIntegrationDraftSerializer(read_only=True)
    merged_from_ids = serializers.PrimaryKeyRelatedField(source="merged_from", many=True, read_only=True)
    formal_modules = serializers.SerializerMethodField()

    class Meta:
        model = RequirementItem
        fields = [
            "id", "project", "project_name", "document", "document_title", "requirement_no",
            "title", "module", "source_module_labels", "formal_modules", "description", "acceptance_criteria",
            "supplementary_description", "priority", "priority_label",
            "confirm_status", "confirm_status_label", "confirmed_by", "confirmed_by_name", "confirmed_at",
            "parse_run", "is_current", "is_archived", "merged_from_ids", "content_blocks",
            "integration_draft", "created_at", "updated_at",
        ]

    def get_formal_modules(self, obj):
        return serialize_modules(obj.formal_modules)
        read_only_fields = [
            "project", "parse_run", "confirm_status", "confirmed_by", "confirmed_at",
            "is_current", "is_archived", "created_at", "updated_at",
        ]


class RequirementVersionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    requirement_items_count = serializers.IntegerField(read_only=True)
    requirement_revisions_count = serializers.SerializerMethodField()
    requirement_items = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    requirement_revisions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = RequirementVersion
        fields = [
            "id", "project", "project_name", "name", "version_no", "sequence", "description",
            "requirement_items", "requirement_revisions", "requirement_items_count", "requirement_revisions_count", "status", "status_label",
            "created_by", "created_by_name", "published_by", "published_at", "created_at", "updated_at",
        ]
        read_only_fields = ["sequence", "status", "created_by", "published_by", "published_at", "created_at", "updated_at"]

    def get_requirement_revisions_count(self, obj):
        if hasattr(obj, "requirement_revisions_count"):
            return obj.requirement_revisions_count
        return obj.requirement_revisions.count()


class RequirementVersionBindingSerializer(serializers.Serializer):
    revision_ids = serializers.PrimaryKeyRelatedField(
        source="revisions",
        queryset=RequirementRevision.objects.select_related("family", "source_item"),
        many=True,
        allow_empty=False,
    )

class RequirementRevisionSerializer(serializers.ModelSerializer):
    family_no = serializers.CharField(source="family.family_no", read_only=True)
    modules = serializers.SerializerMethodField()
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)

    class Meta:
        model = RequirementRevision
        fields = [
            "id", "family", "family_no", "source_item", "previous_revision", "revision_no",
            "change_type", "title", "modules", "description", "acceptance_criteria",
            "supplementary_description", "source_summary", "source_content_hash",
            "confirmed_by", "confirmed_by_name", "confirmed_at",
        ]
        read_only_fields = fields

    def get_modules(self, obj):
        return serialize_modules(obj.modules)


class RequirementFamilySerializer(serializers.ModelSerializer):
    modules = serializers.SerializerMethodField()
    latest_revision = serializers.SerializerMethodField()

    class Meta:
        model = RequirementFamily
        fields = ["id", "project", "modules", "family_no", "title", "status", "latest_revision", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def get_latest_revision(self, obj):
        revision = obj.revisions.order_by("-revision_no", "-id").first()
        return RequirementRevisionSerializer(revision).data if revision else None

    def get_modules(self, obj):
        return serialize_modules(obj.modules)


class RequirementMatchCandidateSerializer(serializers.ModelSerializer):
    revision = RequirementRevisionSerializer(read_only=True)

    class Meta:
        model = RequirementMatchCandidate
        fields = ["id", "revision", "keyword_rank", "vector_rank", "rrf_rank", "matched_excerpt", "rationale"]


class RequirementIntegrationEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementIntegrationEvidence
        fields = ["id", "usage", "asset_type", "asset_id", "asset_revision_id", "chunk_id", "source_locator", "excerpt", "created_at"]


class RequirementConflictSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementConflict
        fields = ["id", "title", "current_statement", "historical_statement", "status", "resolution", "final_statement", "resolved_by", "resolved_at"]
        read_only_fields = ["resolved_by", "resolved_at"]


class RequirementOpenQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementOpenQuestion
        fields = ["id", "category", "question", "status", "answer", "handled_by", "handled_at"]
        read_only_fields = ["handled_by", "handled_at"]


class RequirementIntegrationRunSerializer(serializers.ModelSerializer):
    match_candidates = RequirementMatchCandidateSerializer(many=True, read_only=True)
    evidence = RequirementIntegrationEvidenceSerializer(many=True, read_only=True)
    conflicts = RequirementConflictSerializer(many=True, read_only=True)
    open_questions = RequirementOpenQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = RequirementIntegrationRun
        fields = [
            "id", "batch", "requirement_item", "status", "source_content_hash",
            "model_name", "prompt_name", "search_snapshot", "error_message", "error_info", "created_by",
            "created_at", "completed_at", "match_candidates", "evidence", "conflicts", "open_questions",
        ]
        read_only_fields = fields


class RequirementIntegrationBatchSerializer(serializers.ModelSerializer):
    runs = RequirementIntegrationRunSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RequirementIntegrationBatch
        fields = ["id", "project", "document", "requirement_items", "status", "status_label", "total_count", "success_count", "failed_count", "error_message", "error_info", "retry_of", "created_by", "created_at", "started_at", "completed_at", "runs"]
        read_only_fields = fields


class TestCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    version_name = serializers.CharField(source="version.name", read_only=True)
    requirement_no = serializers.CharField(source="requirement_item.requirement_no", read_only=True)
    requirement_title = serializers.CharField(source="requirement_item.title", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    test_type_label = serializers.CharField(source="get_test_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    enhancement_history = serializers.SerializerMethodField()

    class Meta:
        model = TestCase
        fields = [
            "id", "project", "project_name", "version", "version_name", "requirement_item",
            "requirement_revision", "requirement_no", "requirement_title", "generation_task", "case_no", "title",
            "preconditions", "steps", "expected_result", "priority", "priority_label",
            "test_type", "test_type_label", "status", "status_label", "generated_by_model",
            "reviewed_by_model", "review_feedback", "raw_content", "created_by",
            "created_by_name", "enhancement_history", "created_at", "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_enhancement_history(self, obj):
        suggestions = (
            TestCaseEnhancementSuggestion.objects.filter(Q(target_case=obj) | Q(applied_case=obj))
            .select_related("task", "decided_by")
            .prefetch_related("evidence")
            .order_by("-created_at", "-id")[:20]
        )
        return [
            {
                "id": suggestion.id,
                "task": suggestion.task_id,
                "task_no": suggestion.task.task_no,
                "action": suggestion.action,
                "action_label": suggestion.get_action_display(),
                "status": suggestion.status,
                "status_label": suggestion.get_status_display(),
                "before_snapshot": suggestion.before_snapshot,
                "proposed_content": suggestion.proposed_content,
                "rationale": suggestion.rationale,
                "review_feedback": suggestion.review_feedback,
                "decision_note": suggestion.decision_note,
                "decided_by_name": suggestion.decided_by.username if suggestion.decided_by else "",
                "decided_at": suggestion.decided_at,
                "evidence": [
                    {"id": item.id, "usage": item.usage, "identifier": item.identifier, "title": item.title, "excerpt": item.excerpt}
                    for item in suggestion.evidence.all()
                ],
            }
            for suggestion in suggestions
        ]

    def validate(self, attrs):
        requirement_item = attrs.get("requirement_item", getattr(self.instance, "requirement_item", None))
        version = attrs.get("version", getattr(self.instance, "version", None))
        if requirement_item and version and requirement_item.project_id != version.project_id:
            raise serializers.ValidationError("用例关联的版本和详细需求必须属于同一项目")
        if requirement_item and version and not attrs.get("requirement_revision", getattr(self.instance, "requirement_revision", None)):
            revision = version.requirement_revisions.filter(source_item=requirement_item).first()
            if revision:
                attrs["requirement_revision"] = revision
        return attrs


class TestCaseGenerationTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    version_name = serializers.CharField(source="version.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    requirement_items = RequirementItemSerializer(many=True, read_only=True)
    requirement_revisions = RequirementRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = TestCaseGenerationTask
        fields = [
            "id", "task_no", "project", "project_name", "version", "version_name",
            "requirement_items", "requirement_revisions", "status", "status_label", "progress", "total_count",
            "success_count", "failed_count", "generation_log", "error_message", "error_info", "retry_of",
            "created_by", "created_by_name", "started_at", "completed_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class TestCaseGenerationRequestSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=ProjectConfig.objects.filter(status="active"))
    version = serializers.PrimaryKeyRelatedField(queryset=RequirementVersion.objects.filter(status="published"))
    requirement_items = serializers.PrimaryKeyRelatedField(queryset=RequirementItem.objects.all(), many=True, allow_empty=False)

    def validate(self, attrs):
        project = attrs["project"]
        version = attrs["version"]
        items = attrs["requirement_items"]
        if version.project_id != project.id:
            raise serializers.ValidationError({"version": "版本不属于当前项目"})
        invalid_project_items = [item.id for item in items if item.project_id != project.id]
        if invalid_project_items:
            raise serializers.ValidationError({"requirement_items": f"详细需求不属于当前项目: {invalid_project_items}"})
        unconfirmed_items = [item.id for item in items if item.confirm_status != "confirmed"]
        if unconfirmed_items:
            raise serializers.ValidationError({"requirement_items": f"详细需求尚未确认: {unconfirmed_items}"})
        revision_item_ids = set(version.requirement_revisions.values_list("source_item_id", flat=True))
        not_in_version = [item.id for item in items if item.id not in revision_item_ids]
        if not_in_version:
            raise serializers.ValidationError({"requirement_items": f"正式需求修订未关联到当前已发布版本: {not_in_version}"})

        missing = []
        for role_type, label in [("testcase_writer", "测试用例生成专家"), ("testcase_reviewer", "测试用例评审专家")]:
            try:
                PromptConfig.resolve_active(role_type, error_class=TestCaseGenerationError)
            except TestCaseGenerationError:
                missing.append(label)
        if missing:
            raise serializers.ValidationError({"configuration": f"缺少可用配置: {'、'.join(missing)}"})
        return attrs


class TestCaseEnhancementEvidenceSerializer(serializers.ModelSerializer):
    usage_label = serializers.CharField(source="get_usage_display", read_only=True)

    class Meta:
        model = TestCaseEnhancementEvidence
        fields = [
            "id", "task", "requirement_revision", "usage", "usage_label", "asset_type",
            "asset_id", "rank", "identifier", "title", "excerpt", "metadata", "created_at",
        ]
        read_only_fields = fields


class TestCaseEnhancementSuggestionSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    requirement_title = serializers.CharField(source="requirement_revision.title", read_only=True)
    target_case_no = serializers.CharField(source="target_case.case_no", read_only=True)
    applied_case_no = serializers.CharField(source="applied_case.case_no", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.username", read_only=True)
    evidence = TestCaseEnhancementEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = TestCaseEnhancementSuggestion
        fields = [
            "id", "task", "requirement_revision", "requirement_title", "action", "action_label",
            "target_case", "target_case_no", "before_hash", "before_snapshot", "proposed_content",
            "rationale", "evidence_basis", "evidence", "review_passed", "review_feedback",
            "status", "status_label", "applied_case", "applied_case_no", "decision_note",
            "decided_by", "decided_by_name", "decided_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TestCaseEnhancementTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    version_name = serializers.CharField(source="version.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    requirement_revisions = RequirementRevisionSerializer(many=True, read_only=True)
    suggestion_count = serializers.IntegerField(read_only=True)
    pending_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TestCaseEnhancementTask
        fields = [
            "id", "task_no", "project", "project_name", "version", "version_name",
            "requirement_revisions", "status", "status_label", "progress", "total_count",
            "success_count", "failed_count", "enhancer_model", "reviewer_model",
            "retrieval_snapshot", "task_log", "error_message", "error_info", "retry_of", "suggestion_count", "pending_count",
            "created_by", "created_by_name", "started_at", "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TestCaseEnhancementRequestSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=ProjectConfig.objects.filter(status="active"))
    version = serializers.PrimaryKeyRelatedField(queryset=RequirementVersion.objects.filter(status="published"))
    requirement_revisions = serializers.PrimaryKeyRelatedField(queryset=RequirementRevision.objects.all(), many=True, allow_empty=False)

    def validate(self, attrs):
        project = attrs["project"]
        version = attrs["version"]
        revisions = attrs["requirement_revisions"]
        if version.project_id != project.id:
            raise serializers.ValidationError({"version": "版本不属于当前项目"})
        bound_ids = set(version.requirement_revisions.values_list("id", flat=True))
        invalid = [revision.id for revision in revisions if revision.family.project_id != project.id or revision.id not in bound_ids]
        if invalid:
            raise serializers.ValidationError({"requirement_revisions": f"正式需求未绑定到目标版本: {invalid}"})
        missing = []
        for role_type, label in (("testcase_enhancer", "测试用例增强专家"), ("testcase_reviewer", "测试用例评审专家")):
            try:
                PromptConfig.resolve_active(role_type, error_class=TestCaseGenerationError)
            except TestCaseGenerationError:
                missing.append(label)
        if missing:
            raise serializers.ValidationError({"configuration": f"缺少可用配置: {'、'.join(missing)}"})
        return attrs


class TestCaseEnhancementDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class TestCaseEnhancementBatchDecisionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    decision = serializers.ChoiceField(choices=["accept", "reject"])
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

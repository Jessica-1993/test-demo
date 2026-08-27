from django.contrib import admin

from .models import (
    RequirementContentBlock, RequirementDocument, RequirementImageAnalysis, RequirementIntegrationDraft,
    RequirementItem, RequirementParseRun, RequirementVersion, TestCase, TestCaseEnhancementEvidence,
    TestCaseEnhancementSuggestion, TestCaseEnhancementTask, TestCaseGenerationTask,
)


@admin.register(RequirementDocument)
class RequirementDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "document_type", "status", "uploaded_by", "created_at"]
    list_filter = ["status", "document_type", "project"]
    search_fields = ["title", "original_filename", "qiniu_key"]


@admin.register(RequirementItem)
class RequirementItemAdmin(admin.ModelAdmin):
    list_display = ["requirement_no", "title", "module", "project", "document", "priority"]
    list_filter = ["module", "priority", "project"]
    search_fields = ["requirement_no", "title", "description"]


@admin.register(RequirementParseRun)
class RequirementParseRunAdmin(admin.ModelAdmin):
    list_display = ["document", "run_no", "status", "requirement_count", "is_current", "created_at"]
    list_filter = ["status", "is_current"]


@admin.register(RequirementContentBlock)
class RequirementContentBlockAdmin(admin.ModelAdmin):
    list_display = ["parse_run", "requirement", "block_type", "order", "source_locator"]
    list_filter = ["block_type"]


@admin.register(RequirementImageAnalysis)
class RequirementImageAnalysisAdmin(admin.ModelAdmin):
    list_display = ["content_block", "status", "model_name", "analyzed_at", "updated_at"]
    list_filter = ["status", "model_name"]


@admin.register(RequirementIntegrationDraft)
class RequirementIntegrationDraftAdmin(admin.ModelAdmin):
    list_display = ["requirement_item", "status", "model_name", "prompt_name", "updated_at"]
    list_filter = ["status", "model_name", "prompt_name"]
    search_fields = ["title", "module", "description", "source_summary", "error_message"]


@admin.register(RequirementVersion)
class RequirementVersionAdmin(admin.ModelAdmin):
    list_display = ["version_no", "name", "project", "status", "created_by", "updated_at"]
    list_filter = ["status", "project"]
    search_fields = ["version_no", "name", "description"]
    filter_horizontal = ["requirement_items"]


@admin.register(TestCaseGenerationTask)
class TestCaseGenerationTaskAdmin(admin.ModelAdmin):
    list_display = ["task_no", "project", "version", "status", "progress", "success_count", "failed_count", "created_at"]
    list_filter = ["status", "project", "version"]
    search_fields = ["task_no", "error_message"]
    filter_horizontal = ["requirement_items"]


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ["case_no", "title", "project", "version", "requirement_item", "priority", "test_type", "status"]
    list_filter = ["project", "version", "priority", "test_type", "status"]
    search_fields = ["case_no", "title", "steps", "expected_result"]


@admin.register(TestCaseEnhancementTask)
class TestCaseEnhancementTaskAdmin(admin.ModelAdmin):
    list_display = ["task_no", "project", "version", "status", "progress", "success_count", "failed_count", "created_at"]
    list_filter = ["project", "version", "status"]
    search_fields = ["task_no", "error_message"]
    filter_horizontal = ["requirement_revisions"]


@admin.register(TestCaseEnhancementEvidence)
class TestCaseEnhancementEvidenceAdmin(admin.ModelAdmin):
    list_display = ["task", "requirement_revision", "usage", "identifier", "rank"]
    list_filter = ["usage", "asset_type"]
    search_fields = ["identifier", "title", "excerpt"]


@admin.register(TestCaseEnhancementSuggestion)
class TestCaseEnhancementSuggestionAdmin(admin.ModelAdmin):
    list_display = ["task", "requirement_revision", "action", "target_case", "review_passed", "status", "decided_by"]
    list_filter = ["action", "review_passed", "status"]
    search_fields = ["rationale", "review_feedback", "decision_note"]
    filter_horizontal = ["evidence"]

from django.contrib import admin

from .models import Defect, DefectImportBatch


@admin.register(Defect)
class DefectAdmin(admin.ModelAdmin):
    list_display = ["defect_no", "title", "project", "severity", "lifecycle_status", "knowledge_status", "updated_at"]
    list_filter = ["project", "severity", "lifecycle_status", "knowledge_status"]
    search_fields = ["defect_no", "title", "description", "root_cause"]
    filter_horizontal = ["modules", "requirement_revisions", "test_cases"]


@admin.register(DefectImportBatch)
class DefectImportBatchAdmin(admin.ModelAdmin):
    list_display = ["filename", "project", "status", "success_count", "failed_count", "created_by", "created_at"]
    list_filter = ["project", "status"]

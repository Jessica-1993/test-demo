from django.db import transaction
from django.utils import timezone
from rest_framework import decorators, permissions, response, status, viewsets

from apps.core.errors import build_error_info

from apps.project_knowledge.models import ProjectModule
from apps.requirements.models import RequirementVersion
from apps.search.services import SearchIndexService

from .models import Defect, DefectImportBatch
from .serializers import (
    DefectConfirmSerializer,
    DefectImportBatchSerializer,
    DefectImportRequestSerializer,
    DefectSerializer,
)
from .services import DefectImportError, DefectImportService


class DefectViewSet(viewsets.ModelViewSet):
    serializer_class = DefectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "severity", "lifecycle_status", "knowledge_status", "detected_version", "modules"]
    search_fields = ["defect_no", "title", "description", "root_cause", "external_id"]
    ordering_fields = ["created_at", "updated_at", "defect_no", "severity"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return (
            Defect.objects.select_related("project", "detected_version", "fixed_version", "created_by", "confirmed_by")
            .prefetch_related("modules", "requirement_revisions", "test_cases")
            .order_by("-updated_at", "-id")
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, knowledge_status="draft")

    def perform_update(self, serializer):
        defect = serializer.save()
        self._sync_index(defect)

    def perform_destroy(self, instance):
        project_id = instance.project_id
        asset_id = instance.id
        instance.delete()
        SearchIndexService.enqueue("defect", asset_id, project_id, user=self.request.user, action="delete")

    @decorators.action(detail=False, methods=["post"])
    def confirm(self, request):
        serializer = DefectConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        defects = list(self.get_queryset().filter(id__in=serializer.validated_data["ids"]))
        found = {item.id for item in defects}
        missing = sorted(set(serializer.validated_data["ids"]) - found)
        if missing:
            return response.Response({"detail": f"缺陷不存在: {missing}"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for defect in defects:
                defect.knowledge_status = "confirmed"
                defect.confirmed_by = request.user
                defect.confirmed_at = timezone.now()
                defect.save(update_fields=["knowledge_status", "confirmed_by", "confirmed_at", "updated_at"])
                SearchIndexService.enqueue("defect", defect.id, defect.project_id, user=request.user)
        return response.Response(self.get_serializer(defects, many=True).data)

    @decorators.action(detail=True, methods=["post"])
    def invalidate(self, request, pk=None):
        defect = self.get_object()
        defect.knowledge_status = "invalid"
        defect.save(update_fields=["knowledge_status", "updated_at"])
        SearchIndexService.enqueue("defect", defect.id, defect.project_id, user=request.user, action="delete")
        return response.Response(self.get_serializer(defect).data)

    @decorators.action(detail=False, methods=["post"], url_path="import")
    def import_file(self, request):
        serializer = DefectImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.validated_data["project"]
        uploaded_file = serializer.validated_data["file"]
        batch = DefectImportBatch.objects.create(project=project, filename=uploaded_file.name, created_by=request.user)
        try:
            rows = DefectImportService.read_rows(uploaded_file)
        except DefectImportError as exc:
            info = build_error_info(
                "VALIDATION_ERROR",
                message=str(exc),
                details={"stage": "缺陷文件导入", "task_no": str(batch.id)},
            )
            batch.status = "failed"
            batch.error_info = info
            batch.errors = [{"row": 0, "detail": info["message"]}]
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "error_info", "errors", "completed_at"])
            return response.Response(DefectImportBatchSerializer(batch).data, status=status.HTTP_400_BAD_REQUEST)

        errors = []
        success_count = 0
        for row_number, payload in rows:
            try:
                normalized = self._normalize_import_payload(project, payload)
                row_serializer = self.get_serializer(data={"project": project.id, **normalized})
                row_serializer.is_valid(raise_exception=True)
                row_serializer.save(created_by=request.user, knowledge_status="draft")
                success_count += 1
            except Exception as exc:
                detail = getattr(exc, "detail", str(exc))
                errors.append({"row": row_number, "detail": detail})
        batch.total_count = len(rows)
        batch.success_count = success_count
        batch.failed_count = len(errors)
        batch.errors = errors[:500]
        batch.status = "partial_success" if success_count and errors else ("completed" if success_count or not rows else "failed")
        batch.completed_at = timezone.now()
        batch.save(update_fields=["total_count", "success_count", "failed_count", "errors", "status", "completed_at"])
        response_status = status.HTTP_201_CREATED if success_count else status.HTTP_400_BAD_REQUEST
        return response.Response(DefectImportBatchSerializer(batch).data, status=response_status)

    @staticmethod
    def _normalize_import_payload(project, payload):
        severity_aliases = {"致命": "critical", "严重": "high", "一般": "medium", "轻微": "low"}
        status_aliases = {"待处理": "open", "已解决": "resolved", "已关闭": "closed", "已拒绝": "rejected"}
        normalized = {key: value for key, value in payload.items() if key not in {"detected_version_no", "fixed_version_no", "module_codes"}}
        normalized["severity"] = severity_aliases.get(str(normalized.get("severity") or "").strip(), normalized.get("severity") or "medium")
        normalized["lifecycle_status"] = status_aliases.get(str(normalized.get("lifecycle_status") or "").strip(), normalized.get("lifecycle_status") or "open")
        tags = normalized.get("tags")
        if isinstance(tags, str):
            normalized["tags"] = [part.strip() for part in tags.replace("，", ",").split(",") if part.strip()]
        for source_field, target_field in (("detected_version_no", "detected_version"), ("fixed_version_no", "fixed_version")):
            version_no = str(payload.get(source_field) or "").strip()
            if version_no:
                version = RequirementVersion.objects.filter(project=project, version_no=version_no).first()
                if not version:
                    raise ValueError(f"版本不存在: {version_no}")
                normalized[target_field] = version.id
        module_codes = str(payload.get("module_codes") or "").replace("，", ",")
        if module_codes.strip():
            codes = [part.strip() for part in module_codes.split(",") if part.strip()]
            modules = list(ProjectModule.objects.filter(project=project, code__in=codes))
            found = {module.code for module in modules}
            missing = sorted(set(codes) - found)
            if missing:
                raise ValueError(f"模块编码不存在: {missing}")
            normalized["modules"] = [module.id for module in modules]
        return normalized

    def _sync_index(self, defect):
        action = "upsert" if defect.knowledge_status == "confirmed" else "delete"
        SearchIndexService.enqueue("defect", defect.id, defect.project_id, user=self.request.user, action=action)


class DefectImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DefectImportBatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status"]

    def get_queryset(self):
        return DefectImportBatch.objects.select_related("project", "created_by").order_by("-created_at", "-id")

import threading
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q
from django.utils import timezone
from apps.core.errors import AppError, build_error_info, error_http_status, error_info_from_exception
from kombu.exceptions import OperationalError
from rest_framework import decorators, permissions, response, serializers, status, viewsets

from apps.configuration.models import ProjectConfig
from apps.project_knowledge.models import ProjectModule

from .models import (
    RequirementConflict, RequirementContentBlock, RequirementDocument, RequirementFamily,
    RequirementIntegrationBatch, RequirementIntegrationDraft, RequirementItem, RequirementOpenQuestion, RequirementParseRun,
    RequirementRevision, RequirementVersion, TestCase, TestCaseEnhancementSuggestion,
    TestCaseEnhancementTask, TestCaseGenerationTask,
)
from .serializers import (
    RequirementConflictSerializer,
    RequirementDocumentSerializer,
    RequirementDocumentUploadSerializer,
    RequirementContentBlockSerializer,
    RequirementIntegrationDraftSerializer,
    RequirementIntegrationBatchSerializer,
    RequirementIntegrationRunSerializer,
    RequirementFamilySerializer,
    RequirementItemSerializer,
    RequirementParseRunSerializer,
    RequirementRevisionSerializer,
    RequirementVersionBindingSerializer,
    RequirementVersionSerializer,
    TestCaseGenerationRequestSerializer,
    TestCaseGenerationTaskSerializer,
    TestCaseEnhancementBatchDecisionSerializer,
    TestCaseEnhancementDecisionSerializer,
    TestCaseEnhancementRequestSerializer,
    TestCaseEnhancementSuggestionSerializer,
    TestCaseEnhancementTaskSerializer,
    TestCaseSerializer,
)
from .integration import RequirementReviewError, RequirementReviewService
from .enhancement import TestCaseEnhancementError, TestCaseEnhancementService
from .services import DocumentExtractionService, QiniuStorageService, RequirementIntegrationService, RequirementParser, StructuredRequirementParser


class RequirementDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status", "document_type"]
    search_fields = ["title", "original_filename", "qiniu_key"]
    ordering_fields = ["created_at", "updated_at", "title"]

    def get_queryset(self):
        return (
            RequirementDocument.objects.select_related("project", "uploaded_by")
            .prefetch_related(Prefetch("parse_runs", queryset=RequirementParseRun.objects.order_by("-run_no"), to_attr="prefetched_runs"))
            .annotate(items_count=Count("items", distinct=True))
            .order_by("-created_at", "-id")
        )

    @decorators.action(detail=False, methods=["post"])
    def upload(self, request):
        serializer = RequirementDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload_file = serializer.validated_data["file"]
        try:
            project = ProjectConfig.objects.get(pk=serializer.validated_data["project"])
        except ProjectConfig.DoesNotExist:
            return response.Response({"detail": "项目不存在"}, status=status.HTTP_400_BAD_REQUEST)
        title = serializer.validated_data.get("title") or upload_file.name
        document_type = RequirementParser.detect_type(upload_file.name)

        try:
            upload_result = QiniuStorageService().upload(upload_file)
        except (ImproperlyConfigured, RuntimeError) as exc:
            code = "STORAGE_CONFIGURATION_MISSING" if isinstance(exc, ImproperlyConfigured) else "STORAGE_UNAVAILABLE"
            raise AppError(code, details={"stage": "需求文档上传"}, cause_detail=str(exc)) from exc

        with transaction.atomic():
            document = RequirementDocument.objects.create(
                project=project,
                title=title,
                original_filename=upload_file.name,
                document_type=document_type,
                file_size=upload_file.size,
                qiniu_key=upload_result["key"],
                qiniu_url=upload_result["url"],
                uploaded_by=request.user,
            )

        return response.Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def parse(self, request, pk=None):
        document = self.get_object()
        run_no = (document.parse_runs.aggregate(value=Max("run_no"))["value"] or 0) + 1
        retry_of = document.parse_runs.filter(status="failed").order_by("-run_no", "-id").first()
        parse_run = RequirementParseRun.objects.create(
            document=document, run_no=run_no, created_by=request.user, retry_of=retry_of,
        )
        try:
            storage = QiniuStorageService()
            content = storage.download(document.qiniu_key, document.qiniu_url)
            extraction = DocumentExtractionService.extract_bytes(
                content, document.document_type, document.original_filename
            )
            organized = StructuredRequirementParser.organize(extraction["blocks"], document.title)
            self._save_parse_result(document, parse_run, extraction, organized, storage)
        except Exception as exc:
            info = error_info_from_exception(
                exc, trace_id=getattr(request, "trace_id", None),
                details={"stage": "文档解析", "task_no": str(parse_run.id)},
                fallback_code="DOCUMENT_PARSE_FAILED",
            )
            parse_run.status = "failed"
            parse_run.message = info["message"]
            parse_run.error_info = info
            parse_run.completed_at = timezone.now()
            parse_run.save(update_fields=["status", "message", "error_info", "completed_at"])
            document.parse_message = f"第 {run_no} 次解析失败：{info['message']}"
            if not document.parse_runs.filter(is_current=True).exists():
                document.status = "failed"
            document.save(update_fields=["status", "parse_message", "updated_at"])
            return response.Response({"error": info, "detail": info["message"], "field_errors": {}, "parse_run": RequirementParseRunSerializer(parse_run).data}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(RequirementParseRunSerializer(parse_run).data)

    @decorators.action(detail=False, methods=["post"])
    def sync_qiniu(self, request):
        project_id = request.data.get("project")
        try:
            project = ProjectConfig.objects.get(pk=project_id)
            objects = QiniuStorageService().list_documents()
        except ProjectConfig.DoesNotExist:
            return response.Response({"detail": "项目不存在"}, status=status.HTTP_400_BAD_REQUEST)
        except (ImproperlyConfigured, RuntimeError) as exc:
            code = "STORAGE_CONFIGURATION_MISSING" if isinstance(exc, ImproperlyConfigured) else "STORAGE_UNAVAILABLE"
            raise AppError(code, details={"stage": "七牛文档同步"}, cause_detail=str(exc)) from exc
        created = updated = skipped = 0
        storage = QiniuStorageService()
        for item in objects:
            key = item.get("key", "")
            filename = key.rsplit("/", 1)[-1]
            document_type = RequirementParser.detect_type(filename)
            if document_type == "other" or "/parsed/" in key:
                skipped += 1
                continue
            document, was_created = RequirementDocument.objects.get_or_create(
                qiniu_key=key,
                defaults={
                    "project": project, "title": filename, "original_filename": filename,
                    "document_type": document_type, "file_size": item.get("fsize", 0),
                    "qiniu_url": storage.public_url(key), "uploaded_by": request.user,
                },
            )
            if was_created:
                created += 1
            else:
                document.file_size = item.get("fsize", document.file_size)
                document.qiniu_url = storage.public_url(key)
                document.save(update_fields=["file_size", "qiniu_url", "updated_at"])
                updated += 1
        return response.Response({"created": created, "updated": updated, "skipped": skipped})

    @decorators.action(detail=True, methods=["get"])
    def content(self, request, pk=None):
        document = self.get_object()
        run = document.parse_runs.filter(is_current=True).first()
        return response.Response({
            "id": document.id,
            "title": document.title,
            "original_filename": document.original_filename,
            "extraction_engine": document.extraction_engine,
            "parse_run": RequirementParseRunSerializer(run).data if run else None,
            "requirements": RequirementItemSerializer(document.items.filter(is_current=True).prefetch_related("content_blocks"), many=True).data,
            "orphan_blocks": RequirementContentBlockSerializer(run.content_blocks.filter(requirement__isnull=True), many=True).data if run else [],
        })

    @decorators.action(detail=True, methods=["get"])
    def parse_runs(self, request, pk=None):
        return response.Response(RequirementParseRunSerializer(self.get_object().parse_runs.all(), many=True).data)

    @decorators.action(detail=True, methods=["post"])
    def integrate_batch(self, request, pk=None):
        document = self.get_object()
        ids = request.data.get("ids") or list(document.items.filter(is_current=True, is_archived=False).values_list("id", flat=True))
        items = document.items.filter(id__in=ids, is_current=True, is_archived=False)
        if not items.exists():
            return response.Response({"ids": "没有可整合的需求"}, status=status.HTTP_400_BAD_REQUEST)
        batch = RequirementIntegrationBatch.objects.create(
            project=document.project, document=document,
            total_count=items.count(), created_by=request.user,
        )
        batch.requirement_items.set(items)
        from .tasks import run_requirement_integration_batch
        run_requirement_integration_batch.delay(batch.id)
        return response.Response(RequirementIntegrationBatchSerializer(batch).data, status=status.HTTP_202_ACCEPTED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if RequirementRevision.objects.filter(source_item__document=instance).exists():
            return response.Response(
                {"detail": "该文档已被正式需求引用，只能归档，不能物理删除"},
                status=status.HTTP_409_CONFLICT,
            )
        image_keys = RequirementContentBlock.objects.filter(
            parse_run__document=instance
        ).exclude(image_key="").values_list("image_key", flat=True)
        try:
            QiniuStorageService().delete_many([instance.qiniu_key, *image_keys])
        except (ImproperlyConfigured, RuntimeError) as exc:
            return response.Response(
                {"detail": f"七牛文件删除失败：{exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @decorators.action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        document = self.get_object()
        document.status = "archived"
        document.save(update_fields=["status", "updated_at"])
        return response.Response(self.get_serializer(document).data)

    @staticmethod
    def _save_parse_result(document, parse_run, extraction, organized, storage):
        table_count = image_count = block_count = 0
        raw_blocks = [{key: value for key, value in block.items() if key != "image_data"} for block in extraction["blocks"]]
        with transaction.atomic():
            document.items.filter(is_current=True).update(is_current=False, is_archived=True)
            document.parse_runs.filter(is_current=True).update(is_current=False)
            created_items = []
            for index, parsed in enumerate(organized["requirements"], start=1):
                item = RequirementItem.objects.create(
                    project=document.project, document=document, parse_run=parse_run,
                    requirement_no=f"REQ-{parse_run.run_no:03d}-{index:03d}", title=parsed["title"][:200],
                    module=parsed["module"][:100],
                    source_module_labels=[parsed["module"][:100]] if parsed["module"].strip() else [],
                    description="\n".join(parsed["description"]).strip(),
                    supplementary_description="\n".join(parsed["supplementary"]).strip(),
                )
                created_items.append((item, parsed["blocks"]))
            all_blocks = [(item, block) for item, blocks in created_items for block in blocks]
            all_blocks.extend((None, block) for block in organized["orphan_blocks"])
            for order, (item, block) in enumerate(all_blocks, start=1):
                image_key = image_url = ""
                if block["block_type"] == "image" and block.get("image_data"):
                    image_key = f"{storage.prefix}/parsed/{document.id}/{parse_run.id}/images/{order}.png"
                    uploaded = storage.upload_bytes(block["image_data"], image_key)
                    image_url = uploaded["url"]
                    image_count += 1
                if block["block_type"] == "table":
                    table_count += 1
                RequirementContentBlock.objects.create(
                    parse_run=parse_run, requirement=item, block_type=block["block_type"], order=order,
                    text=block.get("text", ""), heading_level=block.get("heading_level"), page=block.get("page"),
                    source_locator=block.get("source_locator", ""), table_data=block.get("table_data", {}),
                    image_key=image_key, image_url=image_url, image_width=block.get("image_width"), image_height=block.get("image_height"),
                )
                block_count += 1
            parse_run.status = "completed"
            parse_run.extraction_engine = extraction["engine"]
            parse_run.message = f"解析完成：{len(created_items)} 条需求，{block_count} 个有效内容块"
            parse_run.block_count = block_count
            parse_run.requirement_count = len(created_items)
            parse_run.table_count = table_count
            parse_run.image_count = image_count
            parse_run.filtered_count = len(organized["filtered"])
            parse_run.filtered_blocks = organized["filtered"]
            parse_run.is_current = True
            parse_run.completed_at = timezone.now()
            parse_run.save()
            document.title = organized["document_title"][:200]
            document.extracted_text = extraction["plain_text"]
            document.extracted_blocks = raw_blocks
            document.extraction_engine = extraction["engine"]
            document.status = "parsed"
            document.parse_message = parse_run.message
            document.save()

class RequirementItemViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "document", "parse_run", "module", "priority"]
    search_fields = ["requirement_no", "title", "description"]
    ordering_fields = ["created_at", "updated_at", "requirement_no", "module"]

    def get_queryset(self):
        queryset = RequirementItem.objects.select_related("project", "document", "parse_run", "integration_draft").prefetch_related(
            "content_blocks", "formal_modules", "integration_draft__formal_modules"
        ).order_by("module", "requirement_no", "id")
        formal_module_id = self.request.query_params.get("formal_module")
        if formal_module_id:
            try:
                root_id = int(formal_module_id)
            except (TypeError, ValueError):
                raise serializers.ValidationError({"formal_module": "必须是有效模块 ID"})
            descendant_ids = {root_id}
            pending = [root_id]
            while pending:
                children = list(ProjectModule.objects.filter(parent_id__in=pending).values_list("id", flat=True))
                new_ids = [module_id for module_id in children if module_id not in descendant_ids]
                descendant_ids.update(new_ids)
                pending = new_ids
            queryset = queryset.filter(formal_modules__id__in=descendant_ids).distinct()
        version_id = self.request.query_params.get("version")
        if version_id:
            queryset = queryset.filter(versions__id=version_id, confirm_status="confirmed")
        elif self.request.query_params.get("include_archived") != "true":
            queryset = queryset.filter(is_current=True, is_archived=False)
        if (
            not version_id
            and self.action == "list"
            and self.request.query_params.get("include_unconfirmed") != "true"
        ):
            queryset = queryset.filter(confirm_status="confirmed")
        return queryset

    def perform_create(self, serializer):
        document = serializer.validated_data["document"]
        module = serializer.validated_data.get("module", "").strip()
        serializer.save(
            project=document.project,
            source_module_labels=[module] if module else [],
            confirm_status="confirmed",
            confirmed_by=self.request.user,
            confirmed_at=timezone.now(),
        )

    def perform_update(self, serializer):
        document = serializer.validated_data.get("document", serializer.instance.document)
        serializer.save(project=document.project)

    def perform_destroy(self, instance):
        instance.is_current = False
        instance.is_archived = True
        instance.save(update_fields=["is_current", "is_archived", "updated_at"])

    @decorators.action(detail=False, methods=["post"])
    def confirm(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return response.Response({"detail": "请至少选择一条需求"}, status=status.HTTP_400_BAD_REQUEST)
        items = list(RequirementItem.objects.filter(id__in=ids).select_related("project"))
        if len(items) != len(set(ids)):
            found_ids = {item.id for item in items}
            missing_ids = [item_id for item_id in ids if item_id not in found_ids]
            return response.Response({"detail": f"需求不存在: {missing_ids}"}, status=status.HTTP_400_BAD_REQUEST)
        invalid_items = [item.id for item in items if not item.is_current or item.is_archived]
        if invalid_items:
            return response.Response({"detail": f"只能确认当前有效且未归档的需求: {invalid_items}"}, status=status.HTTP_400_BAD_REQUEST)
        if len({item.project_id for item in items}) != 1:
            return response.Response({"detail": "只能批量确认同一项目下的需求"}, status=status.HTTP_400_BAD_REQUEST)
        revisions = []
        try:
            for item in items:
                revisions.append(RequirementReviewService.confirm(item, request.user))
        except RequirementReviewError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(RequirementRevisionSerializer(revisions, many=True).data)

    @decorators.action(detail=False, methods=["post"])
    def merge(self, request):
        ids = request.data.get("ids") or []
        items = list(RequirementItem.objects.filter(id__in=ids, is_current=True).select_related("document", "parse_run").prefetch_related("content_blocks"))
        if len(items) < 2:
            return response.Response({"detail": "请至少选择两条当前需求"}, status=status.HTTP_400_BAD_REQUEST)
        if len({item.document_id for item in items}) != 1 or len({item.parse_run_id for item in items}) != 1:
            return response.Response({"detail": "只能合并同一解析批次的需求"}, status=status.HTTP_400_BAD_REQUEST)
        invalid = [
            item.id for item in items
            if item.confirm_status == "confirmed"
            or hasattr(item, "integration_draft")
            or RequirementRevision.objects.filter(source_item=item).exists()
        ]
        if invalid:
            return response.Response({"detail": f"已进入整合或正式确认的需求不能合并: {invalid}"}, status=status.HTTP_409_CONFLICT)
        items.sort(key=lambda item: item.requirement_no)
        source_labels = []
        seen_labels = set()
        for item in items:
            for label in (item.source_module_labels or [item.module]):
                normalized = str(label).strip().casefold()
                if normalized and normalized not in seen_labels:
                    seen_labels.add(normalized)
                    source_labels.append(str(label).strip())
        with transaction.atomic():
            merged = RequirementItem.objects.create(
                project=items[0].project, document=items[0].document, parse_run=items[0].parse_run,
                requirement_no=f"MERGE-{timezone.now():%H%M%S%f}", title=request.data.get("title") or items[0].title,
                module=request.data.get("module") or items[0].module,
                source_module_labels=source_labels,
                description="\n\n".join(item.description for item in items if item.description),
                supplementary_description="\n\n".join(item.supplementary_description for item in items if item.supplementary_description),
            )
            merged.merged_from.set(items)
            order = 1
            for item in items:
                for block in item.content_blocks.all():
                    block.pk = None
                    block.requirement = merged
                    block.order = order
                    block.save()
                    order += 1
            RequirementItem.objects.filter(id__in=ids).update(is_current=False, is_archived=True)
        return response.Response(self.get_serializer(merged).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def reorder_blocks(self, request, pk=None):
        item = self.get_object()
        block_ids = request.data.get("block_ids") or []
        owned_ids = set(item.content_blocks.values_list("id", flat=True))
        if set(block_ids) != owned_ids:
            return response.Response({"detail": "内容块列表必须完整且属于当前需求"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for order, block_id in enumerate(block_ids, start=1):
                RequirementContentBlock.objects.filter(pk=block_id).update(order=order)
        return response.Response(self.get_serializer(item).data)

    @decorators.action(detail=True, methods=["get", "patch"])
    def integration(self, request, pk=None):
        item = self.get_object()
        try:
            draft = item.integration_draft
        except Exception:
            return response.Response({"detail": "暂无需求整合稿"}, status=status.HTTP_404_NOT_FOUND)
        if request.method == "GET":
            latest_run = item.integration_runs.filter(status="completed").first()
            return response.Response({
                "draft": RequirementIntegrationDraftSerializer(draft).data,
                "run": RequirementIntegrationRunSerializer(latest_run).data if latest_run else None,
            })
        serializer = RequirementIntegrationDraftSerializer(draft, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return response.Response(serializer.data)

    @decorators.action(detail=True, methods=["post"])
    def integrate(self, request, pk=None):
        item = self.get_object()
        try:
            run = RequirementReviewService.integrate(item, request.user)
        except Exception as exc:
            info = error_info_from_exception(
                exc, trace_id=getattr(request, "trace_id", None),
                details={"stage": "需求整合", "resource": str(item.id)},
            )
            try:
                draft = item.integration_draft
            except Exception:
                draft = None
            payload = {"error": info, "detail": info["message"], "field_errors": {}}
            if draft:
                payload["integration_draft"] = RequirementIntegrationDraftSerializer(draft).data
            return response.Response(payload, status=error_http_status(info["code"]))
        return response.Response(RequirementIntegrationRunSerializer(run).data)

    @decorators.action(detail=True, methods=["post"])
    def confirm_relationship(self, request, pk=None):
        item = self.get_object()
        try:
            draft = item.integration_draft
        except RequirementIntegrationDraft.DoesNotExist:
            return response.Response({"detail": "暂无需求整合稿"}, status=status.HTTP_404_NOT_FOUND)
        mode = request.data.get("relationship_mode")
        if mode not in {"new", "existing"}:
            return response.Response({"relationship_mode": "必须是 new 或 existing"}, status=status.HTTP_400_BAD_REQUEST)
        family = None
        if mode == "existing":
            family = RequirementFamily.objects.filter(pk=request.data.get("selected_family"), project=item.project).first()
            if not family:
                return response.Response({"selected_family": "请选择当前项目的需求族"}, status=status.HTTP_400_BAD_REQUEST)
        draft.relationship_mode = mode
        draft.selected_family = family
        draft.change_type = request.data.get("change_type") or ("initial" if mode == "new" else "modified")
        draft.relationship_confirmed = True
        draft.updated_by = request.user
        draft.save(update_fields=["relationship_mode", "selected_family", "change_type", "relationship_confirmed", "updated_by", "updated_at"])
        return response.Response(RequirementIntegrationDraftSerializer(draft).data)

    @decorators.action(detail=True, methods=["post"])
    def review_integration(self, request, pk=None):
        item = self.get_object()
        try:
            draft = item.integration_draft
        except RequirementIntegrationDraft.DoesNotExist:
            return response.Response({"detail": "暂无需求整合稿"}, status=status.HTTP_404_NOT_FOUND)
        review_status = request.data.get("review_status")
        if review_status not in {"approved", "rejected"}:
            return response.Response({"review_status": "必须是 approved 或 rejected"}, status=status.HTTP_400_BAD_REQUEST)
        if review_status == "approved":
            selected_count = draft.formal_modules.count()
            active_count = draft.formal_modules.filter(status="active", project=item.project).count()
            if not selected_count:
                return response.Response({"formal_module_ids": "请至少选择一个启用的正式模块"}, status=status.HTTP_409_CONFLICT)
            if active_count != selected_count:
                return response.Response({"formal_module_ids": "所选模块包含已停用或不属于当前项目的节点"}, status=status.HTTP_409_CONFLICT)
            if draft.unresolved_module_paths or draft.module_resolution_status != "resolved":
                return response.Response({"module_resolution_status": "存在未解决的模块路径"}, status=status.HTTP_409_CONFLICT)
            if not draft.relationship_confirmed:
                return response.Response({"relationship_confirmed": "请先人工确认需求关系"}, status=status.HTTP_409_CONFLICT)
            run = item.integration_runs.filter(status="completed").first()
            if run and run.conflicts.filter(status="pending").exists():
                return response.Response({"conflicts": "存在未处理的需求冲突"}, status=status.HTTP_409_CONFLICT)
        draft.review_status = review_status
        draft.reviewed_by = request.user
        draft.reviewed_at = timezone.now()
        draft.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "updated_at"])
        return response.Response(RequirementIntegrationDraftSerializer(draft).data)

    @decorators.action(detail=True, methods=["post"])
    def confirm_formal(self, request, pk=None):
        try:
            revision = RequirementReviewService.confirm(self.get_object(), request.user)
        except RequirementReviewError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(RequirementRevisionSerializer(revision).data, status=status.HTTP_201_CREATED)


class RequirementContentBlockViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementContentBlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = RequirementContentBlock.objects.select_related("parse_run", "requirement")

    def perform_destroy(self, instance):
        instance.delete()


class RequirementVersionViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementVersionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status"]
    search_fields = ["name", "version_no", "description"]
    ordering_fields = ["created_at", "updated_at", "name", "version_no"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return (
            RequirementVersion.objects.select_related("project", "created_by")
            .prefetch_related("requirement_items", "requirement_revisions")
            .annotate(
                requirement_items_count=Count("requirement_items", distinct=True),
                requirement_revisions_count=Count("requirement_revisions", distinct=True),
            )
            .order_by("-updated_at", "-id")
        )

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        sequence = (RequirementVersion.objects.filter(project=project).aggregate(value=Max("sequence"))["value"] or 0) + 1
        serializer.save(
            created_by=self.request.user,
            sequence=sequence,
            status="draft",
        )

    def _validated_revisions(self, request, version):
        serializer = RequirementVersionBindingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revisions = serializer.validated_data["revisions"]
        invalid_ids = [revision.id for revision in revisions if revision.family.project_id != version.project_id]
        if invalid_ids:
            return None, response.Response(
                {"revision_ids": f"正式需求修订不属于当前项目: {invalid_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return revisions, None

    @decorators.action(detail=True, methods=["post"])
    def bind_requirements(self, request, pk=None):
        with transaction.atomic():
            current_version = self.get_object()
            version = self.get_queryset().select_for_update().get(pk=current_version.pk)
            if version.status == "archived":
                return response.Response({"detail": "归档版本不能再绑定需求"}, status=status.HTTP_409_CONFLICT)
            revisions, error_response = self._validated_revisions(request, version)
            if error_response:
                return error_response
            version.requirement_revisions.add(*revisions)
            version.requirement_items.add(*(revision.source_item for revision in revisions))
        return response.Response(self.get_serializer(self.get_queryset().get(pk=version.pk)).data)

    @decorators.action(detail=True, methods=["post"])
    def unbind_requirements(self, request, pk=None):
        with transaction.atomic():
            current_version = self.get_object()
            version = self.get_queryset().select_for_update().get(pk=current_version.pk)
            if version.status != "draft":
                return response.Response({"detail": "只有待发布版本可以移除需求"}, status=status.HTTP_409_CONFLICT)
            revisions, error_response = self._validated_revisions(request, version)
            if error_response:
                return error_response
            version.requirement_revisions.remove(*revisions)
            version.requirement_items.remove(*(revision.source_item for revision in revisions))
        return response.Response(self.get_serializer(self.get_queryset().get(pk=version.pk)).data)

    @decorators.action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        with transaction.atomic():
            current_version = self.get_object()
            version = self.get_queryset().select_for_update().get(pk=current_version.pk)
            if version.status != "draft":
                return response.Response({"detail": "只有待发布版本可以发布"}, status=status.HTTP_409_CONFLICT)
            if not version.requirement_revisions.exists():
                return response.Response({"detail": "请至少绑定一条正式需求后再发布"}, status=status.HTTP_409_CONFLICT)
            version.status = "published"
            version.published_by = request.user
            version.published_at = timezone.now()
            version.save(update_fields=["status", "published_by", "published_at", "updated_at"])
        return response.Response(self.get_serializer(self.get_queryset().get(pk=version.pk)).data)

    @decorators.action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        version = self.get_object()
        if version.status != "published":
            return response.Response({"detail": "只能归档已发布版本"}, status=status.HTTP_409_CONFLICT)
        version.status = "archived"
        version.save(update_fields=["status", "updated_at"])
        return response.Response(self.get_serializer(version).data)


class RequirementFamilyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RequirementFamilySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status"]
    search_fields = ["family_no", "title"]

    def get_queryset(self):
        queryset = RequirementFamily.objects.select_related("project").prefetch_related("modules", "revisions__modules")
        module_id = self.request.query_params.get("module")
        if module_id:
            queryset = queryset.filter(modules__id__in=self._module_scope(module_id)).distinct()
        return queryset

    @staticmethod
    def _module_scope(module_id):
        scope = {int(module_id)}
        frontier = list(scope)
        while frontier:
            children = list(ProjectModule.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
            frontier = [pk for pk in children if pk not in scope]
            scope.update(frontier)
        return scope


class RequirementRevisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RequirementRevisionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["family", "change_type", "versions"]
    search_fields = ["family__family_no", "title", "description"]

    def get_queryset(self):
        queryset = RequirementRevision.objects.select_related("family__project", "source_item", "confirmed_by").prefetch_related("modules")
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(family__project_id=project_id)
        module_id = self.request.query_params.get("module")
        if module_id:
            try:
                scope = RequirementFamilyViewSet._module_scope(module_id)
            except (TypeError, ValueError):
                raise serializers.ValidationError({"module": "必须是有效模块 ID"})
            queryset = queryset.filter(modules__id__in=scope).distinct()
        return queryset


class RequirementConflictViewSet(viewsets.GenericViewSet):
    serializer_class = RequirementConflictSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = RequirementConflict.objects.select_related("run", "resolved_by")

    @decorators.action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        conflict = self.get_object()
        serializer = self.get_serializer(conflict, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        resolution = serializer.validated_data.get("resolution", conflict.resolution)
        final_statement = serializer.validated_data.get("final_statement", conflict.final_statement)
        if resolution not in {"current", "historical", "manual"} or not final_statement:
            return response.Response({"detail": "请选择处理方式并填写最终规则"}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(status="resolved", resolved_by=request.user, resolved_at=timezone.now())
        return response.Response(serializer.data)


class RequirementOpenQuestionViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = RequirementOpenQuestion.objects.select_related("run", "handled_by")

    @decorators.action(detail=True, methods=["post"])
    def handle(self, request, pk=None):
        question = self.get_object()
        question.status = request.data.get("status", "answered")
        question.answer = request.data.get("answer", "")
        question.handled_by = request.user
        question.handled_at = timezone.now()
        question.save(update_fields=["status", "answer", "handled_by", "handled_at"])
        from .serializers import RequirementOpenQuestionSerializer
        return response.Response(RequirementOpenQuestionSerializer(question).data)


class TestCaseViewSet(viewsets.ModelViewSet):
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "version", "requirement_item", "priority", "test_type", "status"]
    search_fields = ["case_no", "title", "steps", "expected_result"]
    ordering_fields = ["created_at", "updated_at", "case_no", "priority"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return (
            TestCase.objects.select_related("project", "version", "requirement_item", "generation_task", "created_by")
            .order_by("-created_at", "-id")
        )

    def perform_create(self, serializer):
        requirement_item = serializer.validated_data["requirement_item"]
        version = serializer.validated_data["version"]
        serializer.save(project=requirement_item.project, version=version, created_by=self.request.user)


class TestCaseGenerationTaskViewSet(viewsets.ModelViewSet):
    serializer_class = TestCaseGenerationTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "version", "status"]
    search_fields = ["task_no", "error_message"]
    ordering_fields = ["created_at", "updated_at", "progress"]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return (
            TestCaseGenerationTask.objects.select_related("project", "version", "created_by")
            .prefetch_related("requirement_items")
            .order_by("-created_at", "-id")
        )

    @decorators.action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = TestCaseGenerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        requested_item_ids = {item.id for item in validated["requirement_items"]}
        active_tasks = (
            TestCaseGenerationTask.objects.filter(
                project=validated["project"],
                version=validated["version"],
                status__in=["pending", "running"],
            )
            .prefetch_related("requirement_items")
            .order_by("-created_at", "-id")
        )
        for active_task in active_tasks:
            active_item_ids = set(active_task.requirement_items.values_list("id", flat=True))
            if active_item_ids == requested_item_ids:
                if (
                    active_task.status == "pending"
                    and not active_task.started_at
                    and active_task.created_at < timezone.now() - timedelta(minutes=2)
                ):
                    active_task.status = "failed"
                    active_task.progress = 100
                    queue_error = build_error_info(
                        "QUEUE_UNAVAILABLE",
                        details={"stage": "任务派发", "task_no": active_task.task_no},
                    )
                    active_task.error_message = queue_error["message"]
                    active_task.error_info = queue_error
                    active_task.completed_at = timezone.now()
                    active_task.generation_log = [{
                        "status": "failed",
                        "stage": "任务派发",
                        "message": active_task.error_message,
                        "error": queue_error,
                    }]
                    active_task.save(update_fields=[
                        "status",
                        "progress",
                        "error_message",
                        "error_info",
                        "completed_at",
                        "generation_log",
                        "updated_at",
                    ])
                    continue
                return response.Response(self.get_serializer(active_task).data, status=status.HTTP_200_OK)

        task_no = f"TCG-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        with transaction.atomic():
            task = TestCaseGenerationTask.objects.create(
                task_no=task_no,
                project=validated["project"],
                version=validated["version"],
                total_count=len(validated["requirement_items"]),
                created_by=request.user,
            )
            task.requirement_items.set(validated["requirement_items"])
            task.requirement_revisions.set(
                validated["version"].requirement_revisions.filter(
                    source_item_id__in=requested_item_ids
                )
            )

        from .tasks import run_testcase_generation_task

        try:
            run_testcase_generation_task.delay(task.id)
        except (ConnectionError, OperationalError):
            threading.Thread(target=run_testcase_generation_task, args=(task.id,), daemon=True).start()
        return response.Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.status not in {"failed", "partial_success"}:
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        active = source.retries.filter(status__in=["pending", "running"]).order_by("-id").first()
        if active:
            return response.Response(self.get_serializer(active).data)
        failed_ids = {
            entry.get("requirement_item") for entry in source.generation_log
            if entry.get("status") == "failed" and entry.get("requirement_item")
        }
        item_ids = failed_ids or set(source.requirement_items.values_list("id", flat=True))
        serializer = TestCaseGenerationRequestSerializer(data={
            "project": source.project_id,
            "version": source.version_id,
            "requirement_items": sorted(item_ids),
        })
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["requirement_items"]
        with transaction.atomic():
            task = TestCaseGenerationTask.objects.create(
                task_no=f"TCG-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                project=source.project,
                version=source.version,
                total_count=len(items),
                created_by=request.user,
                retry_of=source,
            )
            task.requirement_items.set(items)
            task.requirement_revisions.set(
                source.version.requirement_revisions.filter(source_item_id__in=item_ids)
            )
        from .tasks import run_testcase_generation_task
        try:
            run_testcase_generation_task.delay(task.id)
        except (ConnectionError, OperationalError):
            threading.Thread(target=run_testcase_generation_task, args=(task.id,), daemon=True).start()
        return response.Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)


class RequirementIntegrationBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RequirementIntegrationBatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "document", "status", "retry_of"]

    def get_queryset(self):
        return (
            RequirementIntegrationBatch.objects.select_related("project", "document", "created_by", "retry_of")
            .prefetch_related("requirement_items", "runs")
            .order_by("-created_at", "-id")
        )

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.status not in {"failed", "partial_success"}:
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        active = source.retries.filter(status__in=["pending", "running"]).order_by("-id").first()
        if active:
            return response.Response(self.get_serializer(active).data)
        failed_ids = set(source.runs.filter(status="failed").values_list("requirement_item_id", flat=True))
        item_ids = failed_ids or set(source.requirement_items.values_list("id", flat=True))
        items = source.document.items.filter(id__in=item_ids, is_current=True, is_archived=False)
        if items.count() != len(item_ids):
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            batch = RequirementIntegrationBatch.objects.create(
                project=source.project,
                document=source.document,
                target_version=source.target_version,
                total_count=len(item_ids),
                created_by=request.user,
                retry_of=source,
            )
            batch.requirement_items.set(items)
        from .tasks import run_requirement_integration_batch
        try:
            run_requirement_integration_batch.delay(batch.id)
        except (ConnectionError, OperationalError):
            threading.Thread(target=run_requirement_integration_batch, args=(batch.id,), daemon=True).start()
        return response.Response(self.get_serializer(batch).data, status=status.HTTP_201_CREATED)


class TestCaseEnhancementTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestCaseEnhancementTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "version", "status"]
    search_fields = ["task_no", "error_message"]
    ordering_fields = ["created_at", "updated_at", "progress"]

    def get_queryset(self):
        return (
            TestCaseEnhancementTask.objects.select_related("project", "version", "created_by")
            .prefetch_related("requirement_revisions__family", "requirement_revisions__source_item")
            .annotate(
                suggestion_count=Count("suggestions", distinct=True),
                pending_count=Count("suggestions", filter=Q(suggestions__status="pending"), distinct=True),
            )
            .order_by("-created_at", "-id")
        )

    @decorators.action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = TestCaseEnhancementRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        revision_ids = {revision.id for revision in validated["requirement_revisions"]}
        active_tasks = self.get_queryset().filter(
            project=validated["project"], version=validated["version"], status__in=["pending", "running"]
        )
        for active_task in active_tasks:
            if set(active_task.requirement_revisions.values_list("id", flat=True)) == revision_ids:
                return response.Response(self.get_serializer(active_task).data)
        with transaction.atomic():
            task = TestCaseEnhancementTask.objects.create(
                task_no=f"TCE-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                project=validated["project"],
                version=validated["version"],
                total_count=len(revision_ids),
                created_by=request.user,
            )
            task.requirement_revisions.set(validated["requirement_revisions"])
        from .tasks import run_testcase_enhancement_task
        try:
            run_testcase_enhancement_task.delay(task.id)
        except (ConnectionError, OperationalError):
            threading.Thread(target=run_testcase_enhancement_task, args=(task.id,), daemon=True).start()
        task.suggestion_count = 0
        task.pending_count = 0
        return response.Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.status not in {"failed", "partial_success"}:
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        active = source.retries.filter(status__in=["pending", "running"]).order_by("-id").first()
        if active:
            return response.Response(self.get_serializer(active).data)
        failed_ids = {
            entry.get("requirement_revision") for entry in source.task_log
            if entry.get("status") == "failed" and entry.get("requirement_revision")
        }
        revision_ids = failed_ids or set(source.requirement_revisions.values_list("id", flat=True))
        serializer = TestCaseEnhancementRequestSerializer(data={
            "project": source.project_id,
            "version": source.version_id,
            "requirement_revisions": sorted(revision_ids),
        })
        serializer.is_valid(raise_exception=True)
        revisions = serializer.validated_data["requirement_revisions"]
        with transaction.atomic():
            task = TestCaseEnhancementTask.objects.create(
                task_no=f"TCE-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                project=source.project,
                version=source.version,
                total_count=len(revisions),
                created_by=request.user,
                retry_of=source,
            )
            task.requirement_revisions.set(revisions)
        from .tasks import run_testcase_enhancement_task
        try:
            run_testcase_enhancement_task.delay(task.id)
        except (ConnectionError, OperationalError):
            threading.Thread(target=run_testcase_enhancement_task, args=(task.id,), daemon=True).start()
        task.suggestion_count = 0
        task.pending_count = 0
        return response.Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)


class TestCaseEnhancementSuggestionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestCaseEnhancementSuggestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task", "requirement_revision", "action", "status", "target_case", "applied_case"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        return (
            TestCaseEnhancementSuggestion.objects.select_related(
                "task__project", "task__version", "requirement_revision", "target_case", "applied_case", "decided_by"
            ).prefetch_related("evidence")
            .order_by("requirement_revision", "id")
        )

    @decorators.action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        serializer = TestCaseEnhancementDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            suggestion = TestCaseEnhancementService.accept(self.get_object(), request.user, serializer.validated_data.get("note", ""))
        except TestCaseEnhancementError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payload = self.get_serializer(self.get_queryset().get(pk=suggestion.pk)).data
        response_status = status.HTTP_409_CONFLICT if suggestion.status == "conflict" else status.HTTP_200_OK
        return response.Response(payload, status=response_status)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = TestCaseEnhancementDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            suggestion = TestCaseEnhancementService.reject(self.get_object(), request.user, serializer.validated_data.get("note", ""))
        except TestCaseEnhancementError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(self.get_serializer(suggestion).data)

    @decorators.action(detail=False, methods=["post"], url_path="batch-decide")
    def batch_decide(self, request):
        serializer = TestCaseEnhancementBatchDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        decision = serializer.validated_data["decision"]
        note = serializer.validated_data.get("note", "")
        queryset = self.get_queryset().filter(id__in=ids)
        found = {item.id: item for item in queryset}
        results = []
        for suggestion_id in ids:
            suggestion = found.get(suggestion_id)
            if not suggestion:
                results.append({"id": suggestion_id, "ok": False, "detail": "建议不存在"})
                continue
            try:
                if decision == "accept":
                    changed = TestCaseEnhancementService.accept(suggestion, request.user, note)
                    ok = changed.status == "accepted"
                    detail = "已接受" if ok else changed.decision_note
                else:
                    changed = TestCaseEnhancementService.reject(suggestion, request.user, note)
                    ok = True
                    detail = "已拒绝"
            except TestCaseEnhancementError as exc:
                ok = False
                detail = str(exc)
            results.append({"id": suggestion_id, "ok": ok, "detail": detail})
        return response.Response({
            "total": len(results),
            "success_count": sum(1 for item in results if item["ok"]),
            "failed_count": sum(1 for item in results if not item["ok"]),
            "results": results,
        })

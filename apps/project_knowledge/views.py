from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import decorators, permissions, response, serializers, status, viewsets

from apps.core.errors import AppError
from apps.search.services import SearchIndexService

from .models import KnowledgeExtractionRun, ProjectKnowledgeItem, ProjectKnowledgeRevision, ProjectModule, ProjectModuleRevision
from .serializers import KnowledgeExtractionRunSerializer, ProjectKnowledgeItemSerializer, ProjectKnowledgeRevisionSerializer, ProjectModuleDraftSerializer, ProjectModuleSerializer


class ProjectModuleViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectModuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "parent", "status"]
    search_fields = ["code", "name", "description", "aliases__alias"]
    ordering_fields = ["sort_order", "name", "created_at"]

    def get_queryset(self):
        return ProjectModule.objects.select_related("project", "parent").prefetch_related(
            "aliases", "revisions__parent", "revisions__created_by", "revisions__confirmed_by"
        )

    @staticmethod
    def _validate_parent(module, parent):
        if not parent:
            return
        if parent.project_id != module.project_id:
            raise serializers.ValidationError({"parent": "上级模块必须属于同一项目"})
        current = parent
        visited = set()
        while current:
            if current.pk == module.pk:
                raise serializers.ValidationError({"parent": "上级模块不能是当前模块或其后代"})
            if current.pk in visited:
                raise serializers.ValidationError({"parent": "模块层级存在循环"})
            visited.add(current.pk)
            current = current.parent

    @staticmethod
    def _validate_sibling_name(module, parent, name):
        duplicates = ProjectModule.objects.filter(
            project_id=module.project_id,
            parent_id=getattr(parent, "id", None),
            name__iexact=name.strip(),
        ).exclude(pk=module.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"name": "同一上级模块下已存在同名模块"})

    def perform_create(self, serializer):
        with transaction.atomic():
            module = serializer.save()
            self._validate_parent(module, module.parent)
            self._validate_sibling_name(module, module.parent, module.name)
            ProjectModuleRevision.objects.create(
                module=module,
                revision_no=1,
                parent=module.parent,
                code=module.code,
                name=module.name,
                description=module.description,
                module_status=module.status,
                sort_order=module.sort_order,
                status="confirmed",
                created_by=self.request.user,
                confirmed_by=self.request.user,
                confirmed_at=timezone.now(),
            )

    def update(self, request, *args, **kwargs):
        module = self.get_object()
        with transaction.atomic():
            module = ProjectModule.objects.select_for_update().get(pk=module.pk)
            pending = module.revisions.select_for_update().filter(status="candidate").first()
            source = pending or module
            payload = {
                "parent": request.data.get("parent", source.parent_id),
                "code": request.data.get("code", source.code),
                "name": request.data.get("name", source.name),
                "description": request.data.get("description", source.description),
                "status": request.data.get("status", source.module_status if pending else source.status),
                "sort_order": request.data.get("sort_order", source.sort_order),
            }
            draft_serializer = ProjectModuleDraftSerializer(data=payload)
            draft_serializer.is_valid(raise_exception=True)
            values = draft_serializer.validated_data
            self._validate_parent(module, values.get("parent"))
            self._validate_sibling_name(module, values.get("parent"), values["name"])
            if values["status"] == "inactive" and module.children.filter(status="active").exists():
                raise serializers.ValidationError({"status": "存在启用的子模块，不能停用当前模块"})
            if pending:
                pending.parent = values.get("parent")
                pending.code = values["code"]
                pending.name = values["name"]
                pending.description = values.get("description", "")
                pending.module_status = values["status"]
                pending.sort_order = values["sort_order"]
                pending.created_by = request.user
                pending.save(update_fields=["parent", "code", "name", "description", "module_status", "sort_order", "created_by", "updated_at"])
            else:
                revision_no = (module.revisions.aggregate(value=Max("revision_no"))["value"] or 0) + 1
                previous = module.revisions.filter(status="confirmed").order_by("-revision_no").first()
                ProjectModuleRevision.objects.create(
                    module=module,
                    revision_no=revision_no,
                    parent=values.get("parent"),
                    code=values["code"],
                    name=values["name"],
                    description=values.get("description", ""),
                    module_status=values["status"],
                    sort_order=values["sort_order"],
                    previous_revision=previous,
                    created_by=request.user,
                )
        module = self.get_queryset().get(pk=module.pk)
        return response.Response(self.get_serializer(module).data)

    @decorators.action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            module = ProjectModule.objects.select_for_update().select_related("project").get(pk=self.get_object().pk)
            pending = module.revisions.select_for_update().filter(status="candidate").first()
            if pending:
                self._validate_parent(module, pending.parent)
                self._validate_sibling_name(module, pending.parent, pending.name)
                if pending.module_status == "inactive" and module.children.filter(status="active").exists():
                    raise serializers.ValidationError({"status": "存在启用的子模块，不能停用当前模块"})
                if ProjectModule.objects.exclude(pk=module.pk).filter(project=module.project, code=pending.code).exists():
                    raise serializers.ValidationError({"code": "当前项目已存在该模块编码"})
                module.revisions.filter(status="confirmed").update(status="superseded")
                module.parent = pending.parent
                module.code = pending.code
                module.name = pending.name
                module.description = pending.description
                module.status = pending.module_status
                module.sort_order = pending.sort_order
                module.save(update_fields=["parent", "code", "name", "description", "status", "sort_order", "updated_at"])
                pending.status = "confirmed"
                pending.confirmed_by = request.user
                pending.confirmed_at = timezone.now()
                pending.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        module = self.get_queryset().get(pk=module.pk)
        return response.Response(self.get_serializer(module).data)

    @decorators.action(detail=False, methods=["get"])
    def tree(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            raise serializers.ValidationError({"project": "必须指定项目"})
        modules = list(self.get_queryset().filter(project_id=project_id).order_by("sort_order", "id"))
        serialized = {module.id: self.get_serializer(module).data for module in modules}
        for node in serialized.values():
            node["children"] = []
        roots = []
        for module in modules:
            node = serialized[module.id]
            if module.parent_id and module.parent_id in serialized:
                serialized[module.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return response.Response(roots)


class ProjectKnowledgeItemViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectKnowledgeItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "module", "category", "status"]
    search_fields = ["code", "title", "revisions__content"]

    def get_queryset(self):
        return ProjectKnowledgeItem.objects.select_related("project", "module").prefetch_related("revisions__evidence")

    def perform_create(self, serializer):
        item = serializer.save()
        ProjectKnowledgeRevision.objects.create(
            item=item,
            revision_no=1,
            title=item.title,
            content=self.request.data.get("content", ""),
            effective_from_version_id=self.request.data.get("effective_from_version") or None,
            created_by=self.request.user,
        )


class ProjectKnowledgeRevisionViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectKnowledgeRevisionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["item", "status", "effective_from_version"]

    def get_queryset(self):
        return ProjectKnowledgeRevision.objects.select_related("item__project", "effective_from_version", "confirmed_by").prefetch_related("evidence")

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        revision_no = (item.revisions.aggregate(value=Max("revision_no"))["value"] or 0) + 1
        previous = item.revisions.filter(status="confirmed").order_by("-revision_no").first()
        serializer.save(revision_no=revision_no, previous_revision=previous, created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status not in {"candidate", "conflict"}:
            raise serializers.ValidationError("已确认或已结束的知识修订不可修改")
        serializer.save()

    @decorators.action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        revision = self.get_object()
        if revision.status == "confirmed":
            return response.Response(self.get_serializer(revision).data)
        if revision.status not in {"candidate", "conflict"}:
            return response.Response({"detail": "只能确认候选或已处理冲突的知识修订"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            ProjectKnowledgeRevision.objects.filter(item=revision.item, status="confirmed").exclude(pk=revision.pk).update(status="superseded")
            revision.status = "confirmed"
            revision.confirmed_by = request.user
            revision.confirmed_at = timezone.now()
            revision.save(update_fields=["status", "confirmed_by", "confirmed_at"])
            SearchIndexService.enqueue("project_knowledge_revision", revision.id, revision.item.project_id, revision.id, request.user)
        return response.Response(self.get_serializer(revision).data)

    @decorators.action(detail=True, methods=["post"])
    def retire(self, request, pk=None):
        revision = self.get_object()
        revision.status = "retired"
        revision.save(update_fields=["status"])
        SearchIndexService.enqueue("project_knowledge_revision", revision.id, revision.item.project_id, revision.id, request.user, action="delete")
        return response.Response(self.get_serializer(revision).data)


class KnowledgeExtractionRunViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeExtractionRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return KnowledgeExtractionRun.objects.select_related("project", "created_by", "retry_of")

    def perform_create(self, serializer):
        run = serializer.save(created_by=self.request.user)
        from .tasks import run_knowledge_extraction
        run_knowledge_extraction.delay(run.id)

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.status not in {"failed", "partial_success"}:
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        active = source.retries.filter(status__in=["pending", "running"]).order_by("-id").first()
        if active:
            return response.Response(self.get_serializer(active).data)
        serializer = self.get_serializer(data={
            "project": source.project_id,
            "source_document_ids": source.source_document_ids,
            "include_confirmed_requirements": source.include_confirmed_requirements,
        })
        serializer.is_valid(raise_exception=True)
        run = serializer.save(created_by=request.user, retry_of=source)
        from .tasks import run_knowledge_extraction
        run_knowledge_extraction.delay(run.id)
        return response.Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

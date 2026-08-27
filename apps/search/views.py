from rest_framework import decorators, permissions, response, status, viewsets

from apps.core.errors import AppError
from .models import SearchIndexJob
from .opensearch import OpenSearchGateway
from .serializers import SearchIndexJobSerializer


class SearchIndexJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SearchIndexJob.objects.select_related("project", "requested_by", "retry_of")
    serializer_class = SearchIndexJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "asset_type", "status", "action"]

    @decorators.action(detail=False, methods=["get"])
    def health(self, request):
        try:
            payload = OpenSearchGateway().health()
        except Exception as exc:
            raise AppError(
                "SEARCH_UNAVAILABLE",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"stage": "OpenSearch 健康检查"},
            ) from exc
        return response.Response({"ok": True, "cluster": payload})

    @decorators.action(detail=False, methods=["post"])
    def reindex(self, request):
        project_id = request.data.get("project")
        if not project_id:
            return response.Response({"detail": "project 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        from .tasks import enqueue_project_reindex
        enqueue_project_reindex.delay(project_id, request.user.id)
        return response.Response({"detail": "已提交全量重建任务"}, status=status.HTTP_202_ACCEPTED)

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.status != "failed" or source.attempt_count < 6:
            raise AppError("STATE_CONFLICT", http_status=status.HTTP_409_CONFLICT)
        active = source.retries.filter(status__in=["pending", "running"]).order_by("-id").first()
        if active:
            return response.Response(self.get_serializer(active).data)
        from .services import SearchIndexService
        job = SearchIndexService.enqueue(
            source.asset_type,
            source.asset_id,
            source.project_id,
            source.revision_id,
            request.user,
            action=source.action,
            content_hash=source.content_hash,
            retry_of=source,
        )
        return response.Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import decorators, permissions, response, serializers, status, viewsets

from .catalog import PROVIDER_DEFAULTS, PROTOCOL_PROVIDERS, USAGE_PROTOCOLS, role_label
from .default_prompts import DEFAULT_ROLE_PROMPTS
from .models import LLMModelConfig, ProjectConfig, ProjectConfigRevision, PromptConfig
from .serializers import (
    LLMModelConfigSerializer,
    ProjectConfigDraftSerializer,
    ProjectConfigSerializer,
    PromptConfigSerializer,
)
from .services import LLMConnectionTester, LLMModelFetcher


class ProjectConfigViewSet(viewsets.ModelViewSet):
    queryset = ProjectConfig.objects.prefetch_related("revisions__created_by", "revisions__confirmed_by").all()
    serializer_class = ProjectConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "is_default"]
    search_fields = ["name", "code", "owner"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def perform_create(self, serializer):
        instance = serializer.save()
        ProjectConfigRevision.objects.create(
            project=instance,
            revision_no=1,
            name=instance.name,
            code=instance.code,
            description=instance.description,
            owner=instance.owner,
            project_status=instance.status,
            status="confirmed",
            created_by=self.request.user,
            confirmed_by=self.request.user,
            confirmed_at=timezone.now(),
        )
        if instance.is_default:
            instance.set_as_default()

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        with transaction.atomic():
            project = ProjectConfig.objects.select_for_update().get(pk=project.pk)
            pending = project.revisions.select_for_update().filter(status="candidate").first()
            source = pending or project
            payload = {
                "name": request.data.get("name", source.name),
                "code": request.data.get("code", source.code),
                "description": request.data.get("description", source.description),
                "owner": request.data.get("owner", source.owner),
                "status": request.data.get("status", source.project_status if pending else source.status),
            }
            draft_serializer = ProjectConfigDraftSerializer(data=payload)
            draft_serializer.is_valid(raise_exception=True)
            values = draft_serializer.validated_data
            if pending:
                pending.name = values["name"]
                pending.code = values["code"]
                pending.description = values.get("description", "")
                pending.owner = values.get("owner", "")
                pending.project_status = values["status"]
                pending.created_by = request.user
                pending.save(update_fields=["name", "code", "description", "owner", "project_status", "created_by", "updated_at"])
            else:
                revision_no = (project.revisions.aggregate(value=Max("revision_no"))["value"] or 0) + 1
                previous = project.revisions.filter(status="confirmed").order_by("-revision_no").first()
                ProjectConfigRevision.objects.create(
                    project=project,
                    revision_no=revision_no,
                    name=values["name"],
                    code=values["code"],
                    description=values.get("description", ""),
                    owner=values.get("owner", ""),
                    project_status=values["status"],
                    previous_revision=previous,
                    created_by=request.user,
                )
            if "is_default" in request.data and bool(request.data["is_default"]) != project.is_default:
                if request.data["is_default"]:
                    if project.status != "active":
                        raise serializers.ValidationError({"is_default": "停用项目不能设为默认项目"})
                    project.set_as_default()
                else:
                    project.is_default = False
                    project.save(update_fields=["is_default", "updated_at"])
        project = self.get_queryset().get(pk=project.pk)
        return response.Response(self.get_serializer(project).data)

    @decorators.action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            project = ProjectConfig.objects.select_for_update().get(pk=self.get_object().pk)
            pending = project.revisions.select_for_update().filter(status="candidate").first()
            if pending:
                if ProjectConfig.objects.exclude(pk=project.pk).filter(code=pending.code).exists():
                    raise serializers.ValidationError({"code": "项目编码已存在"})
                project.revisions.filter(status="confirmed").update(status="superseded")
                project.name = pending.name
                project.code = pending.code
                project.description = pending.description
                project.owner = pending.owner
                project.status = pending.project_status
                if project.status == "inactive":
                    project.is_default = False
                project.save(update_fields=["name", "code", "description", "owner", "status", "is_default", "updated_at"])
                pending.status = "confirmed"
                pending.confirmed_by = request.user
                pending.confirmed_at = timezone.now()
                pending.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        project = self.get_queryset().get(pk=project.pk)
        return response.Response(self.get_serializer(project).data)

    @decorators.action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        project = self.get_object()
        if project.status != "active":
            return response.Response({"detail": "停用项目不能设为默认项目"}, status=status.HTTP_400_BAD_REQUEST)
        project.set_as_default()
        return response.Response(self.get_serializer(project).data)


class LLMModelConfigViewSet(viewsets.ModelViewSet):
    queryset = LLMModelConfig.objects.all()
    serializer_class = LLMModelConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["provider", "protocol", "usage", "is_active", "is_default"]
    search_fields = ["name", "model_name", "base_url"]
    ordering_fields = ["created_at", "updated_at", "name"]

    @decorators.action(detail=False, methods=["get"], url_path="provider-defaults")
    def provider_defaults(self, request):
        return response.Response({
            "providers": PROVIDER_DEFAULTS,
            "protocol_providers": PROTOCOL_PROVIDERS,
            "usage_protocols": USAGE_PROTOCOLS,
        })

    @decorators.action(detail=False, methods=["post"], url_path="fetch-models")
    def fetch_models(self, request):
        protocol = request.data.get("protocol")
        provider = request.data.get("provider")
        base_url = request.data.get("base_url")
        api_key = request.data.get("api_key")
        usage = request.data.get("usage")

        if not protocol or not provider or not base_url or not api_key or not usage:
            return response.Response({"detail": "usage、protocol、provider、base_url、api_key 都不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if protocol not in USAGE_PROTOCOLS.get(usage, []):
            return response.Response({"detail": "所选用途不支持该协议"}, status=status.HTTP_400_BAD_REQUEST)
        if provider not in PROTOCOL_PROVIDERS.get(protocol, []):
            return response.Response({"detail": "供应商和协议不匹配"}, status=status.HTTP_400_BAD_REQUEST)

        result = LLMModelFetcher(protocol, provider, base_url, api_key, usage).fetch()
        failure_status = result.get("status_code")
        if failure_status == 429:
            failure_status = status.HTTP_429_TOO_MANY_REQUESTS
        elif failure_status == 503:
            failure_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif failure_status != 502:
            failure_status = status.HTTP_502_BAD_GATEWAY
        http_status = status.HTTP_200_OK if result["ok"] else failure_status
        return response.Response(result, status=http_status)

    @decorators.action(detail=False, methods=["get"])
    def active(self, request):
        usage = request.query_params.get("usage")
        queryset = self.get_queryset().filter(is_active=True)
        if usage:
            queryset = queryset.filter(usage=usage)
        model_config = queryset.filter(is_default=True).first() or queryset.first()
        if not model_config:
            return response.Response({"detail": "没有可用的大模型配置"}, status=status.HTTP_404_NOT_FOUND)
        return response.Response(self.get_serializer(model_config).data)

    @decorators.action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        model_config = self.get_object()
        if not model_config.is_active:
            return response.Response({"detail": "停用模型不能设为默认模型"}, status=status.HTTP_400_BAD_REQUEST)
        model_config.set_as_default()
        return response.Response(self.get_serializer(model_config).data)

    @decorators.action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        model_config = self.get_object()
        result = LLMConnectionTester(model_config).test()
        failure_status = result.get("status_code")
        if failure_status not in {400, 401, 403, 404, 429, 500, 502, 503, 504}:
            failure_status = status.HTTP_502_BAD_GATEWAY
        http_status = status.HTTP_200_OK if result["ok"] else failure_status
        return response.Response(result, status=http_status)

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_destroy(self, instance):
        if instance.system_roles.exists():
            raise serializers.ValidationError({"detail": "模型已被系统角色绑定，不能删除"})
        instance.delete()


class PromptConfigViewSet(viewsets.ModelViewSet):
    queryset = PromptConfig.objects.select_related("llm_model").all()
    serializer_class = PromptConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["role_type", "is_active", "llm_model"]
    search_fields = ["name", "prompt_content", "llm_model__name", "llm_model__model_name"]
    ordering_fields = ["created_at", "updated_at", "name"]

    @decorators.action(detail=False, methods=["get"], url_path="default-prompt")
    def default_prompt(self, request):
        role_type = request.query_params.get("role_type")
        if role_type not in DEFAULT_ROLE_PROMPTS:
            return response.Response({"detail": "未知的系统角色类型"}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response({
            "role_type": role_type,
            "role_type_label": role_label(role_type),
            "prompt_content": DEFAULT_ROLE_PROMPTS[role_type],
            "prompt_required": role_type != "embedding",
        })

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

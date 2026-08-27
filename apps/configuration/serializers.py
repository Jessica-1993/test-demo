from rest_framework import serializers

from .catalog import PROVIDER_DEFAULTS, PROTOCOL_PROVIDERS, USAGE_PROTOCOLS
from .models import LLMModelConfig, ProjectConfig, ProjectConfigRevision, PromptConfig


class ProjectConfigRevisionSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    project_status_label = serializers.CharField(source="get_project_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)

    class Meta:
        model = ProjectConfigRevision
        fields = [
            "id", "revision_no", "name", "code", "description", "owner",
            "project_status", "project_status_label", "status", "status_label",
            "previous_revision", "created_by_name", "confirmed_by_name",
            "confirmed_at", "created_at", "updated_at",
        ]


class ProjectConfigDraftSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    code = serializers.SlugField(max_length=80)
    description = serializers.CharField(required=False, allow_blank=True)
    owner = serializers.CharField(required=False, allow_blank=True, max_length=80)
    status = serializers.ChoiceField(choices=ProjectConfig.STATUS_CHOICES)


class ProjectConfigSerializer(serializers.ModelSerializer):
    confirmation_status = serializers.SerializerMethodField()
    pending_revision = serializers.SerializerMethodField()
    current_revision_no = serializers.SerializerMethodField()

    class Meta:
        model = ProjectConfig
        fields = [
            "id",
            "name",
            "code",
            "description",
            "owner",
            "status",
            "is_default",
            "created_at",
            "updated_at",
            "confirmation_status",
            "pending_revision",
            "current_revision_no",
        ]
        read_only_fields = ["created_at", "updated_at", "confirmation_status", "pending_revision", "current_revision_no"]

    def _revisions(self, obj):
        return list(obj.revisions.all())

    def get_pending_revision(self, obj):
        revision = next((item for item in self._revisions(obj) if item.status == "candidate"), None)
        return ProjectConfigRevisionSerializer(revision).data if revision else None

    def get_confirmation_status(self, obj):
        return "pending" if self.get_pending_revision(obj) else "confirmed"

    def get_current_revision_no(self, obj):
        revision = next((item for item in self._revisions(obj) if item.status == "confirmed"), None)
        return revision.revision_no if revision else 0

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", "active"))
        is_default = attrs.get("is_default", getattr(self.instance, "is_default", False))
        if is_default and status == "inactive":
            raise serializers.ValidationError("停用项目不能设为默认项目")
        return attrs


class LLMModelConfigSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_key_masked = serializers.SerializerMethodField(read_only=True)
    provider_label = serializers.CharField(source="get_provider_display", read_only=True)
    usage_label = serializers.CharField(source="get_usage_display", read_only=True)
    protocol_label = serializers.CharField(source="get_protocol_display", read_only=True)

    class Meta:
        model = LLMModelConfig
        fields = [
            "id",
            "name",
            "provider",
            "provider_label",
            "protocol",
            "protocol_label",
            "usage",
            "usage_label",
            "model_name",
            "base_url",
            "api_key",
            "api_key_masked",
            "max_tokens",
            "temperature",
            "top_p",
            "embedding_dimension",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "api_key_masked"]

    def get_api_key_masked(self, obj):
        if not obj.api_key:
            return ""
        if len(obj.api_key) <= 8:
            return "*" * len(obj.api_key)
        return f"{obj.api_key[:4]}{'*' * 8}{obj.api_key[-4:]}"

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        protocol = attrs.get("protocol", getattr(self.instance, "protocol", None))
        usage = attrs.get("usage", getattr(self.instance, "usage", "general_chat"))
        if provider == "custom":
            raise serializers.ValidationError("自定义模型已移除，请选择已支持的供应商")
        if provider and not protocol:
            attrs["protocol"] = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["chatgpt"])["protocol"]
            protocol = attrs["protocol"]

        if provider and protocol and provider not in PROTOCOL_PROVIDERS.get(protocol, []):
            raise serializers.ValidationError("供应商和协议不匹配")
        if protocol and protocol not in USAGE_PROTOCOLS.get(usage, []):
            raise serializers.ValidationError({"protocol": "所选用途不支持该协议"})

        if "temperature" in attrs and not 0 <= attrs["temperature"] <= 2:
            raise serializers.ValidationError("temperature 必须在 0 到 2 之间")
        if "top_p" in attrs and not 0 <= attrs["top_p"] <= 1:
            raise serializers.ValidationError("top_p 必须在 0 到 1 之间")
        dimension = attrs.get("embedding_dimension", getattr(self.instance, "embedding_dimension", 768))
        if usage == "embedding" and dimension not in {768, 1536, 3072}:
            raise serializers.ValidationError({"embedding_dimension": "Gemini Embedding 2 仅允许配置 768、1536 或 3072 维"})
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        is_default = attrs.get("is_default", getattr(self.instance, "is_default", False))
        if is_default and is_active is False:
            raise serializers.ValidationError("停用模型不能设为默认模型")
        if self.instance:
            active_roles = self.instance.system_roles.filter(is_active=True)
            if usage != self.instance.usage and active_roles.exists():
                raise serializers.ValidationError({"usage": "模型已绑定启用角色，请先调整角色配置"})
            if is_active is False and active_roles.exists():
                raise serializers.ValidationError({"is_active": "模型已绑定启用角色，不能停用"})
        return attrs

    def create(self, validated_data):
        if not validated_data.get("api_key"):
            raise serializers.ValidationError({"api_key": "API Key 不能为空"})
        if not validated_data.get("base_url"):
            provider = validated_data.get("provider", "chatgpt")
            validated_data["base_url"] = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["chatgpt"])["base_url"]
        instance = super().create(validated_data)
        if instance.is_default:
            instance.set_as_default()
        return instance

    def update(self, instance, validated_data):
        if not validated_data.get("api_key"):
            validated_data.pop("api_key", None)
        if not validated_data.get("base_url"):
            provider = validated_data.get("provider", instance.provider)
            validated_data["base_url"] = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["chatgpt"])["base_url"]
        instance = super().update(instance, validated_data)
        if instance.is_default:
            instance.set_as_default()
        return instance


class PromptConfigSerializer(serializers.ModelSerializer):
    prompt_content = serializers.CharField(allow_blank=True)
    role_type_label = serializers.CharField(source="get_role_type_display", read_only=True)
    llm_model_name = serializers.CharField(source="llm_model.name", read_only=True)
    llm_model_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PromptConfig
        fields = [
            "id",
            "name",
            "role_type",
            "role_type_label",
            "prompt_content",
            "llm_model",
            "llm_model_name",
            "llm_model_display",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_llm_model_display(self, obj):
        if not obj.llm_model:
            return ""
        return f"{obj.llm_model.name} / {obj.llm_model.model_name}"

    def validate(self, attrs):
        role_type = attrs.get("role_type", getattr(self.instance, "role_type", None))
        prompt_content = attrs.get("prompt_content", getattr(self.instance, "prompt_content", ""))
        llm_model = attrs.get("llm_model", getattr(self.instance, "llm_model", None))
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if role_type != "embedding" and not (prompt_content or "").strip():
            raise serializers.ValidationError({"prompt_content": "提示词内容不能为空"})
        if llm_model and llm_model.usage != role_type:
            raise serializers.ValidationError({"llm_model": "只能绑定与角色类型用途一致的大模型"})
        if is_active and not llm_model:
            raise serializers.ValidationError({"llm_model": "启用系统角色必须绑定大模型"})
        if llm_model and not llm_model.is_active:
            raise serializers.ValidationError({"llm_model": "系统角色不能绑定停用模型"})
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        if instance.is_active:
            instance.activate()
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.is_active:
            instance.activate()
        return instance

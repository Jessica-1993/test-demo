from rest_framework import serializers

from .models import (
    KnowledgeExtractionRun,
    ProjectKnowledgeEvidence,
    ProjectKnowledgeItem,
    ProjectKnowledgeRevision,
    ProjectModule,
    ProjectModuleAlias,
    ProjectModuleRevision,
)


class ProjectModuleAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectModuleAlias
        fields = ["id", "alias"]


class ProjectModuleRevisionSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    module_status_label = serializers.CharField(source="get_module_status_display", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)

    class Meta:
        model = ProjectModuleRevision
        fields = [
            "id", "revision_no", "parent", "parent_name", "code", "name",
            "description", "module_status", "module_status_label", "sort_order",
            "status", "status_label", "previous_revision", "created_by_name",
            "confirmed_by_name", "confirmed_at", "created_at", "updated_at",
        ]


class ProjectModuleDraftSerializer(serializers.Serializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=ProjectModule.objects.all(), required=False, allow_null=True)
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=ProjectModule.STATUS_CHOICES)
    sort_order = serializers.IntegerField(min_value=0)


class ProjectModuleSerializer(serializers.ModelSerializer):
    aliases = ProjectModuleAliasSerializer(many=True, read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    confirmation_status = serializers.SerializerMethodField()
    pending_revision = serializers.SerializerMethodField()
    current_revision_no = serializers.SerializerMethodField()
    path = serializers.CharField(read_only=True)

    class Meta:
        model = ProjectModule
        fields = ["id", "project", "parent", "parent_name", "code", "name", "path", "description", "status", "sort_order", "aliases", "created_at", "updated_at", "confirmation_status", "pending_revision", "current_revision_no"]
        read_only_fields = ["created_at", "updated_at", "confirmation_status", "pending_revision", "current_revision_no"]

    def _revisions(self, obj):
        return list(obj.revisions.all())

    def get_pending_revision(self, obj):
        revision = next((item for item in self._revisions(obj) if item.status == "candidate"), None)
        return ProjectModuleRevisionSerializer(revision).data if revision else None

    def get_confirmation_status(self, obj):
        return "pending" if self.get_pending_revision(obj) else "confirmed"

    def get_current_revision_no(self, obj):
        revision = next((item for item in self._revisions(obj) if item.status == "confirmed"), None)
        return revision.revision_no if revision else 0

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        project = attrs.get("project", getattr(self.instance, "project", None))
        if parent and parent.project_id != getattr(project, "id", None):
            raise serializers.ValidationError({"parent": "上级模块必须属于同一项目"})
        if self.instance and parent and parent.pk == self.instance.pk:
            raise serializers.ValidationError({"parent": "模块不能将自己设为上级"})
        return attrs


class ProjectKnowledgeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectKnowledgeEvidence
        fields = ["id", "source_type", "source_id", "source_revision_id", "source_locator", "excerpt", "created_at"]


class ProjectKnowledgeRevisionSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)
    evidence = ProjectKnowledgeEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectKnowledgeRevision
        fields = ["id", "item", "revision_no", "title", "content", "effective_from_version", "previous_revision", "status", "status_label", "model_name", "created_by", "confirmed_by", "confirmed_by_name", "confirmed_at", "created_at", "evidence"]
        read_only_fields = ["revision_no", "created_by", "confirmed_by", "confirmed_at", "created_at"]


class ProjectKnowledgeItemSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    current_revision = serializers.SerializerMethodField()

    class Meta:
        model = ProjectKnowledgeItem
        fields = ["id", "project", "module", "module_name", "code", "category", "category_label", "title", "tags", "status", "current_revision", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at", "current_revision"]

    def get_current_revision(self, obj):
        revision = obj.revisions.order_by("-revision_no", "-id").first()
        return ProjectKnowledgeRevisionSerializer(revision).data if revision else None


class KnowledgeExtractionRunSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = KnowledgeExtractionRun
        fields = ["id", "project", "source_document_ids", "include_confirmed_requirements", "status", "status_label", "candidate_count", "model_name", "error_message", "error_info", "retry_of", "created_by", "created_at", "completed_at"]
        read_only_fields = ["status", "candidate_count", "model_name", "error_message", "error_info", "retry_of", "created_by", "created_at", "completed_at"]

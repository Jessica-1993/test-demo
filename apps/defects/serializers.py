from rest_framework import serializers

from apps.configuration.models import ProjectConfig

from .models import Defect, DefectImportBatch


class DefectSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    lifecycle_status_label = serializers.CharField(source="get_lifecycle_status_display", read_only=True)
    knowledge_status_label = serializers.CharField(source="get_knowledge_status_display", read_only=True)
    detected_version_name = serializers.CharField(source="detected_version.name", read_only=True)
    fixed_version_name = serializers.CharField(source="fixed_version.name", read_only=True)
    module_paths = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.username", read_only=True)

    class Meta:
        model = Defect
        fields = [
            "id", "project", "project_name", "defect_no", "title", "description",
            "reproduction_steps", "actual_result", "expected_result", "root_cause", "resolution",
            "severity", "severity_label", "lifecycle_status", "lifecycle_status_label",
            "knowledge_status", "knowledge_status_label", "detected_version", "detected_version_name",
            "fixed_version", "fixed_version_name", "modules", "module_paths", "requirement_revisions",
            "test_cases", "tags", "external_source", "external_id", "created_by", "created_by_name",
            "confirmed_by", "confirmed_by_name", "confirmed_at", "created_at", "updated_at",
        ]
        read_only_fields = ["knowledge_status", "created_by", "confirmed_by", "confirmed_at", "created_at", "updated_at"]

    def get_module_paths(self, obj):
        return [{"id": module.id, "path": module.path} for module in obj.modules.all()]

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        for field in ("detected_version", "fixed_version"):
            version = attrs.get(field, getattr(self.instance, field, None))
            if version and project and version.project_id != project.id:
                raise serializers.ValidationError({field: "版本必须属于当前项目"})
        relation_checks = [
            ("modules", "project_id"),
            ("requirement_revisions", "family__project_id"),
            ("test_cases", "project_id"),
        ]
        for field, project_lookup in relation_checks:
            values = attrs.get(field)
            if values is not None and project:
                invalid = [value.id for value in values if self._project_id(value, project_lookup) != project.id]
                if invalid:
                    raise serializers.ValidationError({field: f"存在不属于当前项目的记录: {invalid}"})
        tags = attrs.get("tags")
        if tags is not None and not isinstance(tags, list):
            raise serializers.ValidationError({"tags": "标签必须是数组"})
        return attrs

    @staticmethod
    def _project_id(instance, lookup):
        value = instance
        for part in lookup.split("__"):
            value = getattr(value, part)
        return value


class DefectImportRequestSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=ProjectConfig.objects.filter(status="active"))
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("导入文件不能超过 10MB")
        if not value.name.lower().endswith((".csv", ".xlsx")):
            raise serializers.ValidationError("仅支持 CSV 或 XLSX 文件")
        return value


class DefectConfirmSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)


class DefectImportBatchSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = DefectImportBatch
        fields = "__all__"
        read_only_fields = [field.name for field in DefectImportBatch._meta.fields]

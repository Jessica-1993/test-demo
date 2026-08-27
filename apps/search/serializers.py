from rest_framework import serializers

from .models import SearchIndexJob


class SearchIndexJobSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SearchIndexJob
        fields = "__all__"
        read_only_fields = [field.name for field in SearchIndexJob._meta.fields]

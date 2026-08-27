from django.contrib import admin

from .models import LLMModelConfig, ProjectConfig, PromptConfig


@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "owner", "status", "is_default", "updated_at"]
    list_filter = ["status", "is_default"]
    search_fields = ["name", "code", "owner"]


@admin.register(LLMModelConfig)
class LLMModelConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "provider", "usage", "model_name", "is_active", "is_default", "updated_at"]
    list_filter = ["provider", "usage", "is_active", "is_default"]
    search_fields = ["name", "model_name", "base_url"]


@admin.register(PromptConfig)
class PromptConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "role_type", "llm_model", "is_active", "updated_at"]
    list_filter = ["role_type", "is_active", "llm_model"]
    search_fields = ["name", "prompt_content", "llm_model__name", "llm_model__model_name"]

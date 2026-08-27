from rest_framework.routers import DefaultRouter

from .views import LLMModelConfigViewSet, ProjectConfigViewSet, PromptConfigViewSet


router = DefaultRouter()
router.register("projects", ProjectConfigViewSet, basename="configuration-project")
router.register("llm-models", LLMModelConfigViewSet, basename="configuration-llm-model")
router.register("prompts", PromptConfigViewSet, basename="configuration-prompt")

urlpatterns = router.urls

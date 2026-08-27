from rest_framework.routers import DefaultRouter

from .views import KnowledgeExtractionRunViewSet, ProjectKnowledgeItemViewSet, ProjectKnowledgeRevisionViewSet, ProjectModuleViewSet


router = DefaultRouter()
router.register("modules", ProjectModuleViewSet, basename="project-module")
router.register("knowledge-items", ProjectKnowledgeItemViewSet, basename="project-knowledge-item")
router.register("knowledge-revisions", ProjectKnowledgeRevisionViewSet, basename="project-knowledge-revision")
router.register("extraction-runs", KnowledgeExtractionRunViewSet, basename="knowledge-extraction-run")

urlpatterns = router.urls

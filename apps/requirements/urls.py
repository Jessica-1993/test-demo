from rest_framework.routers import DefaultRouter

from .views import (RequirementConflictViewSet, RequirementContentBlockViewSet,
                    RequirementDocumentViewSet, RequirementFamilyViewSet,
                    RequirementItemViewSet, RequirementOpenQuestionViewSet,
                    RequirementIntegrationBatchViewSet,
                    RequirementRevisionViewSet, RequirementVersionViewSet,
                    TestCaseGenerationTaskViewSet, TestCaseViewSet)
from .views import TestCaseEnhancementSuggestionViewSet, TestCaseEnhancementTaskViewSet


router = DefaultRouter()
router.register("documents", RequirementDocumentViewSet, basename="requirement-document")
router.register("items", RequirementItemViewSet, basename="requirement-item")
router.register("content-blocks", RequirementContentBlockViewSet, basename="requirement-content-block")
router.register("versions", RequirementVersionViewSet, basename="requirement-version")
router.register("families", RequirementFamilyViewSet, basename="requirement-family")
router.register("revisions", RequirementRevisionViewSet, basename="requirement-revision")
router.register("conflicts", RequirementConflictViewSet, basename="requirement-conflict")
router.register("open-questions", RequirementOpenQuestionViewSet, basename="requirement-open-question")
router.register("test-cases", TestCaseViewSet, basename="requirement-test-case")
router.register("generation-tasks", TestCaseGenerationTaskViewSet, basename="requirement-generation-task")
router.register("integration-batches", RequirementIntegrationBatchViewSet, basename="requirement-integration-batch")
router.register("enhancement-tasks", TestCaseEnhancementTaskViewSet, basename="requirement-enhancement-task")
router.register("enhancement-suggestions", TestCaseEnhancementSuggestionViewSet, basename="requirement-enhancement-suggestion")

urlpatterns = router.urls

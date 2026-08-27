from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DefectImportBatchViewSet, DefectViewSet


router = DefaultRouter()
router.register("import-batches", DefectImportBatchViewSet, basename="defect-import-batch")

defect_list = DefectViewSet.as_view({"get": "list", "post": "create"})
defect_detail = DefectViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
defect_import = DefectViewSet.as_view({"post": "import_file"})
defect_confirm = DefectViewSet.as_view({"post": "confirm"})
defect_invalidate = DefectViewSet.as_view({"post": "invalidate"})

urlpatterns = [
    path("", defect_list, name="defect-list"),
    path("import/", defect_import, name="defect-import"),
    path("confirm/", defect_confirm, name="defect-confirm"),
    path("<int:pk>/invalidate/", defect_invalidate, name="defect-invalidate"),
    path("<int:pk>/", defect_detail, name="defect-detail"),
] + router.urls

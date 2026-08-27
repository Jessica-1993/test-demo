from rest_framework.routers import DefaultRouter

from .views import SearchIndexJobViewSet


router = DefaultRouter()
router.register("index-jobs", SearchIndexJobViewSet, basename="search-index-job")

urlpatterns = router.urls

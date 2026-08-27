import hashlib

from django.conf import settings

from apps.core.errors import ClassifiedError

from .models import SearchIndexJob


class SearchUnavailableError(ClassifiedError):
    default_code = "SEARCH_UNAVAILABLE"


class SearchIndexService:
    @staticmethod
    def enqueue(
        asset_type,
        asset_id,
        project_id,
        revision_id=None,
        user=None,
        action="upsert",
        content_hash="",
        dispatch=True,
        retry_of=None,
    ):
        job = SearchIndexJob.objects.create(
            project_id=project_id,
            asset_type=asset_type,
            asset_id=asset_id,
            revision_id=revision_id,
            action=action,
            content_hash=content_hash,
            target_index=settings.OPENSEARCH_INDEX_ALIAS,
            requested_by=user,
            retry_of=retry_of,
        )
        if dispatch:
            from .tasks import run_search_index_job
            transaction_id = job.id
            from django.db import transaction
            transaction.on_commit(lambda: run_search_index_job.delay(transaction_id))
        return job

    @staticmethod
    def content_hash(value):
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

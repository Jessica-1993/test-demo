from celery import chain, shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.errors import error_info_from_exception

from .models import SearchIndexJob
from .opensearch import OpenSearchGateway
from .services import SearchIndexService


@shared_task(bind=True, max_retries=5)
def run_search_index_job(self, job_id):
    job = SearchIndexJob.objects.get(pk=job_id)
    if job.status == "success":
        return
    job.status = "running"
    job.started_at = timezone.now()
    job.attempt_count += 1
    job.error_message = ""
    job.error_info = {}
    job.save(update_fields=["status", "started_at", "attempt_count", "error_message", "error_info", "updated_at"])
    try:
        gateway = OpenSearchGateway()
        if job.action == "delete":
            gateway.delete_asset(job.asset_type, job.asset_id)
        else:
            gateway.upsert_asset(job.asset_type, job.asset_id)
    except Exception as exc:
        info = error_info_from_exception(
            exc, details={"stage": "OpenSearch 索引", "task_no": str(job.id)},
            fallback_code="SEARCH_UNAVAILABLE",
        )
        job.status = "failed"
        job.error_message = info["message"]
        job.error_info = info
        job.save(update_fields=["status", "error_message", "error_info", "updated_at"])
        raise self.retry(exc=exc, countdown=min(60 * (2 ** (job.attempt_count - 1)), 900))
    job.status = "success"
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "updated_at"])


@shared_task
def enqueue_project_reindex(project_id, user_id=None):
    from apps.defects.models import Defect
    from apps.project_knowledge.models import ProjectKnowledgeRevision
    from apps.requirements.models import RequirementRevision, TestCase

    user = get_user_model().objects.filter(pk=user_id).first() if user_id else None
    assets = [
        ("project_knowledge_revision", revision.id, revision.id)
        for revision in ProjectKnowledgeRevision.objects.filter(item__project_id=project_id, status="confirmed")
    ]
    assets += [("requirement_revision", revision.id, revision.id) for revision in RequirementRevision.objects.filter(family__project_id=project_id)]
    assets += [("test_case", case.id, case.requirement_revision_id) for case in TestCase.objects.filter(project_id=project_id, status="active", requirement_revision__isnull=False)]
    assets += [("defect", defect.id, None) for defect in Defect.objects.filter(project_id=project_id, knowledge_status="confirmed")]
    jobs = [
        SearchIndexService.enqueue(
            asset_type,
            asset_id,
            project_id,
            revision_id,
            user,
            dispatch=False,
        )
        for asset_type, asset_id, revision_id in assets
    ]
    if jobs:
        chain(*(run_search_index_job.si(job.id) for job in jobs)).delay()
    return [job.id for job in jobs]

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.configuration.models import LLMModelConfig, ProjectConfig, PromptConfig
from apps.project_knowledge.models import ProjectKnowledgeItem, ProjectKnowledgeRevision

from .models import SearchIndexJob
from .opensearch import EmbeddingService
from .services import SearchIndexService, SearchUnavailableError
from .tasks import enqueue_project_reindex


User = get_user_model()


class SearchIndexDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="search-tester", password="password")
        self.project = ProjectConfig.objects.create(name="索引项目", code="search-project")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("apps.search.tasks.run_search_index_job.delay")
    def test_single_asset_enqueue_dispatches_after_commit(self, mocked_delay):
        with self.captureOnCommitCallbacks(execute=True):
            job = SearchIndexService.enqueue("project_knowledge_revision", 1, self.project.id, 1, self.user)

        mocked_delay.assert_called_once_with(job.id)

    @patch("apps.search.tasks.chain")
    @patch("apps.search.tasks.run_search_index_job.si", side_effect=lambda job_id: f"job-{job_id}")
    def test_project_reindex_dispatches_assets_as_one_serial_chain(self, mocked_signature, mocked_chain):
        first_item = ProjectKnowledgeItem.objects.create(
            project=self.project,
            code="KN-001",
            category="business_rule",
            title="规则一",
        )
        second_item = ProjectKnowledgeItem.objects.create(
            project=self.project,
            code="KN-002",
            category="business_rule",
            title="规则二",
        )
        first_revision = ProjectKnowledgeRevision.objects.create(
            item=first_item,
            revision_no=1,
            title="规则一",
            content="规则一正文",
            status="confirmed",
            created_by=self.user,
        )
        second_revision = ProjectKnowledgeRevision.objects.create(
            item=second_item,
            revision_no=1,
            title="规则二",
            content="规则二正文",
            status="confirmed",
            created_by=self.user,
        )
        chain_result = mocked_chain.return_value

        job_ids = enqueue_project_reindex.run(self.project.id, self.user.id)

        jobs = list(SearchIndexJob.objects.filter(id__in=job_ids).order_by("id"))
        self.assertEqual(len(jobs), 2)
        self.assertEqual({job.asset_id for job in jobs}, {first_revision.id, second_revision.id})
        mocked_signature.assert_any_call(jobs[0].id)
        mocked_signature.assert_any_call(jobs[1].id)
        mocked_chain.assert_called_once_with(f"job-{jobs[0].id}", f"job-{jobs[1].id}")
        chain_result.delay.assert_called_once_with()

    @patch("apps.search.tasks.run_search_index_job.delay")
    def test_exhausted_failed_job_can_create_manual_retry(self, mocked_delay):
        source = SearchIndexJob.objects.create(
            project=self.project,
            asset_type="requirement_revision",
            asset_id=17,
            revision_id=17,
            action="upsert",
            status="failed",
            attempt_count=6,
            requested_by=self.user,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("search-index-job-retry", args=[source.id]), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        retry_job = SearchIndexJob.objects.get(pk=response.data["id"])
        self.assertEqual(retry_job.retry_of_id, source.id)
        self.assertEqual(retry_job.asset_id, source.asset_id)
        mocked_delay.assert_called_once_with(retry_job.id)


class EmbeddingRoleTests(TestCase):
    def test_embedding_config_is_resolved_from_active_role(self):
        model = LLMModelConfig.objects.create(
            name="embedding",
            provider="gemini",
            protocol="gemini",
            usage="embedding",
            model_name="gemini-embedding-2",
            base_url="https://generativelanguage.googleapis.com",
            api_key="secret",
        )
        role = PromptConfig.objects.get(role_type="embedding")
        role.llm_model = model
        role.is_active = True
        role.save(update_fields=["llm_model", "is_active", "updated_at"])

        self.assertEqual(EmbeddingService.active_config(), model)

    def test_embedding_model_without_active_role_is_not_used_as_fallback(self):
        LLMModelConfig.objects.create(
            name="embedding",
            provider="gemini",
            protocol="gemini",
            usage="embedding",
            model_name="gemini-embedding-2",
            base_url="https://generativelanguage.googleapis.com",
            api_key="secret",
            is_default=True,
        )

        with self.assertRaises(SearchUnavailableError):
            EmbeddingService.active_config()

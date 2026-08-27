from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.configuration.models import LLMModelConfig, ProjectConfig, PromptConfig
from apps.project_knowledge.models import ProjectModule

from .enhancement import TestCaseEnhancementService
from .models import (
    RequirementDocument,
    RequirementFamily,
    RequirementItem,
    RequirementRevision,
    RequirementVersion,
    TestCase,
    TestCaseEnhancementSuggestion,
    TestCaseEnhancementTask,
)


User = get_user_model()


class TestCaseEnhancementTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="enhancer", password="password")
        self.client.force_authenticate(self.user)
        self.project = ProjectConfig.objects.create(name="增强项目", code="enhance-project")
        self.module = ProjectModule.objects.create(project=self.project, code="auth", name="认证")
        self.document = RequirementDocument.objects.create(
            project=self.project, title="登录需求", original_filename="login.md", qiniu_key="docs/login-enhance.md", uploaded_by=self.user,
        )
        self.item = RequirementItem.objects.create(
            project=self.project, document=self.document, requirement_no="REQ-001", title="登录", module="认证",
            description="用户使用账号密码登录", acceptance_criteria="错误密码提示失败", confirm_status="confirmed",
            confirmed_by=self.user, confirmed_at=timezone.now(),
        )
        self.family = RequirementFamily.objects.create(project=self.project, family_no="FR-001", title="登录", created_by=self.user)
        self.revision = RequirementRevision.objects.create(
            family=self.family, source_item=self.item, revision_no=1, change_type="initial", title="登录",
            description=self.item.description, acceptance_criteria=self.item.acceptance_criteria,
            source_content_hash="a" * 64, confirmed_by=self.user,
        )
        self.family.modules.set([self.module])
        self.revision.modules.set([self.module])
        self.version = RequirementVersion.objects.create(
            project=self.project, name="版本一", version_no="v1", sequence=2, status="published",
            created_by=self.user, published_by=self.user, published_at=timezone.now(),
        )
        self.version.requirement_items.set([self.item])
        self.version.requirement_revisions.set([self.revision])
        self.case = TestCase.objects.create(
            project=self.project, version=self.version, requirement_item=self.item, requirement_revision=self.revision,
            case_no="TC-001", title="登录成功", steps="输入正确密码", expected_result="进入首页",
            created_by=self.user,
        )
        self.task = TestCaseEnhancementTask.objects.create(
            task_no="TCE-TEST", project=self.project, version=self.version, total_count=1, created_by=self.user,
            enhancer_model="enhancer-model", reviewer_model="reviewer-model",
        )
        self.task.requirement_revisions.set([self.revision])

    def _suggestion(self, action="update", target=None):
        target = self.case if target is None and action == "update" else target
        return TestCaseEnhancementSuggestion.objects.create(
            task=self.task,
            requirement_revision=self.revision,
            action=action,
            target_case=target,
            before_hash=TestCaseEnhancementService.case_hash(target) if target else "",
            before_snapshot=TestCaseEnhancementService.case_snapshot(target) if target else {},
            proposed_content={
                "case_no": "TC-002" if action == "add" else target.case_no,
                "title": "验证错误密码提示",
                "preconditions": "账号存在",
                "steps": "输入错误密码并提交",
                "expected_result": "提示账号或密码错误",
                "priority": "high",
                "test_type": "functional",
            },
            rationale="覆盖异常登录",
            evidence_basis="requirement",
            review_passed=True,
            review_feedback="通过",
        )

    def _seed_roles(self):
        enhancer_model = LLMModelConfig.objects.create(
            name="enhancer", provider="deepseek", protocol="openai_compatible", usage="testcase_enhancer",
            model_name="enhancer-model", base_url="https://example.com", api_key="key",
        )
        reviewer_model = LLMModelConfig.objects.create(
            name="reviewer", provider="deepseek", protocol="openai_compatible", usage="testcase_reviewer",
            model_name="reviewer-model", base_url="https://example.com", api_key="key",
        )
        PromptConfig.objects.update_or_create(role_type="testcase_enhancer", defaults={"name": "增强", "prompt_content": "增强", "llm_model": enhancer_model, "is_active": True})
        PromptConfig.objects.update_or_create(role_type="testcase_reviewer", defaults={"name": "评审", "prompt_content": "评审", "llm_model": reviewer_model, "is_active": True})

    @patch("apps.requirements.enhancement.SearchIndexService.enqueue")
    def test_accept_update_overwrites_case_and_preserves_snapshot(self, enqueue):
        suggestion = self._suggestion()
        result = TestCaseEnhancementService.accept(suggestion, self.user)
        self.case.refresh_from_db()
        self.assertEqual(result.status, "accepted")
        self.assertEqual(self.case.title, "验证错误密码提示")
        self.assertEqual(result.before_snapshot["title"], "登录成功")
        enqueue.assert_called_once()

    def test_concurrent_case_change_marks_conflict(self):
        suggestion = self._suggestion()
        self.case.title = "人工已修改"
        self.case.save(update_fields=["title", "updated_at"])
        result = TestCaseEnhancementService.accept(suggestion, self.user)
        self.assertEqual(result.status, "conflict")
        self.case.refresh_from_db()
        self.assertEqual(self.case.title, "人工已修改")

    @patch("apps.requirements.enhancement.SearchIndexService.enqueue")
    def test_accept_add_creates_new_case(self, enqueue):
        suggestion = self._suggestion(action="add", target=None)
        result = TestCaseEnhancementService.accept(suggestion, self.user)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.applied_case.case_no, "TC-002")
        self.assertEqual(TestCase.objects.filter(version=self.version, requirement_item=self.item).count(), 2)

    def test_generate_endpoint_requires_enhancer_role(self):
        response = self.client.post(reverse("requirement-enhancement-task-generate"), {
            "project": self.project.id,
            "version": self.version.id,
            "requirement_revisions": [self.revision.id],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("configuration", response.data)

    @patch("apps.requirements.tasks.run_testcase_enhancement_task.delay")
    def test_retry_creates_new_task_and_reuses_active_retry(self, mocked_delay):
        self._seed_roles()
        self.task.status = "failed"
        self.task.task_log = [{
            "requirement_revision": self.revision.id,
            "status": "failed",
            "stage": "模型生成",
            "message": "模型服务当前繁忙",
        }]
        self.task.save(update_fields=["status", "task_log", "updated_at"])

        first = self.client.post(reverse("requirement-enhancement-task-retry", args=[self.task.id]), format="json")
        second = self.client.post(reverse("requirement-enhancement-task-retry", args=[self.task.id]), format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        retry_task = TestCaseEnhancementTask.objects.get(pk=first.data["id"])
        self.assertEqual(retry_task.retry_of_id, self.task.id)
        self.assertEqual(list(retry_task.requirement_revisions.values_list("id", flat=True)), [self.revision.id])
        self.assertEqual(second.data["id"], retry_task.id)
        mocked_delay.assert_called_once_with(retry_task.id)

    @patch("apps.requirements.enhancement.OpenSearchGateway.hybrid_search")
    @patch("apps.requirements.enhancement.LLMChatService.chat")
    def test_enhancement_filters_current_version_case_and_saves_defect_evidence(self, chat, hybrid_search):
        self._seed_roles()
        current_case_hit = {"_score": 1, "_source": {"asset_id": 999, "identifier": "TC-CURRENT", "title": "当前", "text": "当前", "version_sequence": 2, "module_ids": [self.module.id]}}
        defect_hit = {"_score": 2, "_source": {"asset_id": 7, "identifier": "BUG-007", "title": "错误密码未提示", "text": "错误密码提交无提示", "version_sequence": 1, "module_ids": [self.module.id]}}
        hybrid_search.side_effect = [[current_case_hit], [defect_hit]]
        chat.side_effect = [
            '{"coverage_analysis":"缺少异常场景","suggestions":[{"action":"add","target_case_id":null,"proposed_content":{"case_no":"TC-002","title":"错误密码","preconditions":"账号存在","steps":"输入错误密码","expected_result":"提示失败","priority":"high","test_type":"functional"},"rationale":"历史缺陷","basis":"evidence","evidence_refs":["defect:7"]}]}',
            '{"results":[{"index":0,"approved":true,"feedback":"通过"}]}',
        ]
        result = TestCaseEnhancementService.enhance_revision(self.task, self.revision)
        self.assertEqual(result["historical_case_count"], 0)
        self.assertEqual(result["defect_count"], 1)
        suggestion = self.task.suggestions.get()
        self.assertEqual(list(suggestion.evidence.values_list("asset_type", "asset_id")), [("defect", 7)])

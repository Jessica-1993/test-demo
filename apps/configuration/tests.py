import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from django.test import SimpleTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.configuration.models import LLMModelConfig, ProjectConfig, ProjectConfigRevision, PromptConfig
from apps.configuration.services import LLMConnectionTester, LLMModelFetcher
from apps.configuration.views import LLMModelConfigViewSet


class FakeUrlopenResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def close(self):
        pass


class ProjectConfigRevisionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="project-admin", password="password")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_is_confirmed_and_edit_waits_for_confirmation(self):
        created = self.client.post(
            reverse("configuration-project-list"),
            {"name": "正式项目", "code": "formal-project", "owner": "甲", "status": "active"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        project = ProjectConfig.objects.get(pk=created.data["id"])
        self.assertEqual(project.revisions.get().status, "confirmed")

        edited = self.client.patch(
            reverse("configuration-project-detail", args=[project.id]),
            {"name": "待确认名称", "owner": "乙"},
            format="json",
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "正式项目")
        self.assertEqual(edited.data["confirmation_status"], "pending")
        self.assertEqual(edited.data["pending_revision"]["name"], "待确认名称")

        self.client.patch(
            reverse("configuration-project-detail", args=[project.id]),
            {"description": "补充说明"},
            format="json",
        )
        self.assertEqual(project.revisions.filter(status="candidate").count(), 1)

        confirmed = self.client.post(reverse("configuration-project-confirm", args=[project.id]))
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "待确认名称")
        self.assertEqual(project.description, "补充说明")
        self.assertEqual(project.revisions.get(status="confirmed").revision_no, 2)
        self.assertEqual(project.revisions.get(revision_no=1).status, "superseded")
        repeated = self.client.post(reverse("configuration-project-confirm", args=[project.id]))
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(project.revisions.count(), 2)

    def test_confirm_revalidates_code_and_disables_default_project(self):
        first = ProjectConfig.objects.create(name="项目一", code="project-one", is_default=True)
        ProjectConfigRevision.objects.create(
            project=first, revision_no=1, name=first.name, code=first.code,
            description="", owner="", project_status="active", status="confirmed",
        )
        ProjectConfig.objects.create(name="项目二", code="project-two")

        conflict = self.client.patch(
            reverse("configuration-project-detail", args=[first.id]),
            {"code": "project-two"}, format="json",
        )
        self.assertEqual(conflict.status_code, status.HTTP_200_OK)
        rejected = self.client.post(reverse("configuration-project-confirm", args=[first.id]))
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        first.refresh_from_db()
        self.assertEqual(first.code, "project-one")

        self.client.patch(
            reverse("configuration-project-detail", args=[first.id]),
            {"code": "project-one", "status": "inactive"}, format="json",
        )
        confirmed = self.client.post(reverse("configuration-project-confirm", args=[first.id]))
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        self.assertEqual(first.status, "inactive")
        self.assertFalse(first.is_default)


class LLMModelFetcherTests(SimpleTestCase):
    @patch("apps.configuration.services.urlopen")
    def test_fetch_gemini_models_accepts_v1beta_base_url(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeUrlopenResponse(
            {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding-004",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            }
        )

        result = LLMModelFetcher(
            "gemini",
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta",
            "secret",
        ).fetch()

        self.assertTrue(result["ok"])
        self.assertEqual(result["models"], ["gemini-2.5-flash"])
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000&key=secret")

    @patch("apps.configuration.services.urlopen")
    def test_fetch_gemini_models_follows_next_page_token(self, mocked_urlopen):
        mocked_urlopen.side_effect = [
            FakeUrlopenResponse(
                {
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ],
                    "nextPageToken": "next token",
                }
            ),
            FakeUrlopenResponse(
                {
                    "models": [
                        {
                            "name": "models/gemini-2.5-pro",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                }
            ),
        ]

        result = LLMModelFetcher(
            "gemini",
            "gemini",
            "https://generativelanguage.googleapis.com",
            "secret",
        ).fetch()

        self.assertTrue(result["ok"])
        self.assertEqual(result["models"], ["gemini-2.5-flash", "gemini-2.5-pro"])
        second_request = mocked_urlopen.call_args_list[1].args[0]
        self.assertIn("pageToken=next%20token", second_request.full_url)

    @patch("apps.configuration.services.urlopen")
    def test_fetch_models_classifies_and_hides_remote_error_message(self, mocked_urlopen):
        body = json.dumps(
            {
                "error": {
                    "code": 400,
                    "message": "API key not valid. Please pass a valid API key.",
                    "status": "INVALID_ARGUMENT",
                }
            }
        ).encode("utf-8")
        mocked_urlopen.side_effect = HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=FakeUrlopenResponse(body),
        )

        result = LLMModelFetcher(
            "gemini",
            "gemini",
            "https://generativelanguage.googleapis.com",
            "invalid",
        ).fetch()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(result["message"], "模型认证失败")
        self.assertEqual(result["error"]["code"], "MODEL_CREDENTIAL_INVALID")
        self.assertNotIn("API key not valid", json.dumps(result, ensure_ascii=False))


class LLMConnectionTesterTests(SimpleTestCase):
    @patch("apps.configuration.services.urlopen")
    def test_openai_responses_connection_posts_to_responses_api(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeUrlopenResponse({"output_text": "pong"})
        config = SimpleNamespace(
            protocol="openai_responses",
            base_url="https://api.openai.com",
            model_name="gpt-5-mini",
            api_key="secret",
            max_tokens=4096,
            temperature=0.1,
            top_p=1,
        )

        result = LLMConnectionTester(config).test()

        self.assertTrue(result["ok"])
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")

    @patch("apps.configuration.services.urlopen")
    def test_gemini_connection_accepts_model_resource_name(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeUrlopenResponse({"candidates": []})
        config = SimpleNamespace(
            protocol="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model_name="models/gemini-2.5-flash",
            api_key="secret",
            max_tokens=4096,
            temperature=0.7,
            top_p=1,
        )

        result = LLMConnectionTester(config).test()

        self.assertTrue(result["ok"])
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=secret")


class LLMModelConfigViewSetTests(SimpleTestCase):
    def test_fetch_models_uses_gateway_status_for_remote_failure(self):
        viewset = LLMModelConfigViewSet()
        viewset.request = SimpleNamespace(
            data={
                "usage": "general_chat",
                "protocol": "gemini",
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com",
                "api_key": "secret",
            }
        )

        with patch("apps.configuration.views.LLMModelFetcher") as mocked_fetcher:
            mocked_fetcher.return_value.fetch.return_value = {
                "ok": False,
                "status_code": 400,
                "message": "获取模型列表失败",
                "response_preview": "{}",
            }
            response = viewset.fetch_models(viewset.request)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class PromptConfigTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="prompt-admin", password="password")
        cls.writer_model = LLMModelConfig.objects.create(
            name="writer",
            provider="deepseek",
            protocol="openai_compatible",
            usage="testcase_writer",
            model_name="writer-model",
            base_url="https://example.com",
            api_key="secret-key",
        )
        cls.reviewer_model = LLMModelConfig.objects.create(
            name="reviewer",
            provider="deepseek",
            protocol="openai_compatible",
            usage="testcase_reviewer",
            model_name="reviewer-model",
            base_url="https://example.com",
            api_key="secret-key",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_all_role_types_are_seeded_by_migration(self):
        configs = PromptConfig.objects.order_by("role_type")

        self.assertEqual(configs.count(), 8)
        self.assertEqual(
            set(configs.values_list("role_type", flat=True)),
            {choice[0] for choice in PromptConfig.ROLE_TYPE_CHOICES},
        )
        self.assertTrue(configs.filter(role_type="testcase_writer", prompt_content__contains="测试用例编写专家").exists())
        self.assertTrue(configs.filter(role_type="testcase_enhancer", prompt_content__contains="增强专家").exists())
        self.assertTrue(configs.filter(role_type="testcase_reviewer", prompt_content__contains="资深测试专家").exists())
        self.assertEqual(configs.filter(is_active=True).count(), 0)

    def test_same_role_type_can_have_multiple_configs(self):
        response = self.client.post(
            reverse("configuration-prompt-list"),
            {
                "name": "备用生成专家",
                "role_type": "testcase_writer",
                "prompt_content": "备用生成提示词",
                "llm_model": self.writer_model.id,
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PromptConfig.objects.filter(role_type="testcase_writer").count(), 2)

    def test_enabling_role_deactivates_other_roles_of_same_type(self):
        current = PromptConfig.objects.get(role_type="testcase_writer")
        current.llm_model = self.writer_model
        current.save(update_fields=["llm_model", "updated_at"])
        alternate = PromptConfig.objects.create(
            name="备用生成专家",
            role_type="testcase_writer",
            prompt_content="备用生成提示词",
            llm_model=self.writer_model,
            is_active=False,
        )

        response = self.client.patch(
            reverse("configuration-prompt-detail", args=[alternate.id]),
            {"is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        current.refresh_from_db()
        alternate.refresh_from_db()
        self.assertFalse(current.is_active)
        self.assertTrue(alternate.is_active)

    def test_prompt_list_supports_filtering_and_pagination(self):
        response = self.client.get(
            reverse("configuration-prompt-list"),
            {"role_type": "testcase_writer", "page": 1, "page_size": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["role_type"], "testcase_writer")
        self.assertEqual(response.data["results"][0]["llm_model_display"], "")

    def test_prompt_can_be_updated(self):
        prompt = PromptConfig.objects.get(role_type="testcase_writer")

        response = self.client.patch(
            reverse("configuration-prompt-detail", args=[prompt.id]),
            {"prompt_content": "更新后的生成提示词", "llm_model": self.writer_model.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prompt.refresh_from_db()
        self.assertEqual(prompt.prompt_content, "更新后的生成提示词")
        self.assertEqual(prompt.llm_model, self.writer_model)
        self.assertEqual(response.data["llm_model_display"], "writer / writer-model")

    def test_active_role_requires_enabled_model(self):
        inactive_model = LLMModelConfig.objects.create(
            name="inactive",
            provider="deepseek",
            protocol="openai_compatible",
            usage="testcase_writer",
            model_name="inactive-model",
            base_url="https://example.com",
            api_key="secret-key",
            is_active=False,
        )

        response = self.client.post(
            reverse("configuration-prompt-list"),
            {
                "name": "不可启用生成专家",
                "role_type": "testcase_writer",
                "prompt_content": "生成提示词",
                "llm_model": inactive_model.id,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("llm_model", response.data)

    def test_role_rejects_model_with_different_usage(self):
        response = self.client.patch(
            reverse("configuration-prompt-detail", args=[PromptConfig.objects.get(role_type="testcase_writer").id]),
            {"llm_model": self.reviewer_model.id, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("llm_model", response.data)

    def test_embedding_role_allows_empty_prompt(self):
        embedding_model = LLMModelConfig.objects.create(
            name="embedding",
            provider="gemini",
            protocol="gemini",
            usage="embedding",
            model_name="gemini-embedding-2",
            base_url="https://generativelanguage.googleapis.com",
            api_key="secret-key",
        )
        prompt = PromptConfig.objects.get(role_type="embedding")

        response = self.client.patch(
            reverse("configuration-prompt-detail", args=[prompt.id]),
            {"prompt_content": "", "llm_model": embedding_model.id, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["prompt_content"], "")

    def test_default_prompt_endpoint_exposes_role_template(self):
        response = self.client.get(
            reverse("configuration-prompt-default-prompt"),
            {"role_type": "vision_analyzer"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["prompt_required"])
        self.assertIn("图片理解", response.data["prompt_content"])

    def test_default_prompt_endpoint_rejects_unknown_role(self):
        response = self.client.get(
            reverse("configuration-prompt-default-prompt"),
            {"role_type": "unknown"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_provider_defaults_exposes_usage_protocol_matrix(self):
        response = self.client.get(reverse("configuration-llm-model-provider-defaults"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["usage_protocols"]["embedding"], ["gemini"])
        self.assertEqual(response.data["protocol_providers"]["openai_responses"], ["chatgpt"])

    def test_model_cannot_be_disabled_while_bound_to_active_role(self):
        prompt = PromptConfig.objects.get(role_type="testcase_writer")
        prompt.llm_model = self.writer_model
        prompt.is_active = True
        prompt.save(update_fields=["llm_model", "is_active", "updated_at"])

        response = self.client.patch(
            reverse("configuration-llm-model-detail", args=[self.writer_model.id]),
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_active", response.data)

    def test_model_cannot_be_deleted_while_bound_to_role(self):
        prompt = PromptConfig.objects.get(role_type="testcase_writer")
        prompt.llm_model = self.writer_model
        prompt.save(update_fields=["llm_model", "updated_at"])

        response = self.client.delete(reverse("configuration-llm-model-detail", args=[self.writer_model.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_text_usage_rejects_responses_protocol(self):
        response = self.client.post(
            reverse("configuration-llm-model-list"),
            {
                "name": "invalid writer",
                "provider": "chatgpt",
                "protocol": "openai_responses",
                "usage": "testcase_writer",
                "model_name": "gpt-5-mini",
                "base_url": "https://api.openai.com",
                "api_key": "secret-key",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("protocol", response.data)

    def test_prompt_can_be_deleted(self):
        prompt = PromptConfig.objects.create(
            name="待删除评审专家",
            role_type="testcase_reviewer",
            prompt_content="评审提示词",
            llm_model=self.reviewer_model,
            is_active=False,
        )

        response = self.client.delete(reverse("configuration-prompt-detail", args=[prompt.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PromptConfig.objects.filter(pk=prompt.id).exists())

    def test_model_update_preserves_api_key(self):
        model = LLMModelConfig.objects.create(
            name="writer",
            provider="gemini",
            protocol="gemini",
            usage="testcase_writer",
            model_name="gemini-test",
            base_url="https://generativelanguage.googleapis.com",
            api_key="secret-key",
        )

        response = self.client.patch(
            reverse("configuration-llm-model-detail", args=[model.id]),
            {"name": "writer updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        model.refresh_from_db()
        self.assertEqual(model.name, "writer updated")
        self.assertEqual(model.api_key, "secret-key")

    def test_vision_analyzer_model_can_use_openai_responses_protocol(self):
        response = self.client.post(
            reverse("configuration-llm-model-list"),
            {
                "name": "OpenAI 图片理解",
                "provider": "chatgpt",
                "protocol": "openai_responses",
                "usage": "vision_analyzer",
                "model_name": "gpt-5-mini",
                "base_url": "https://api.openai.com",
                "api_key": "secret-key",
                "max_tokens": 4096,
                "temperature": 0.1,
                "top_p": 1,
                "is_active": True,
                "is_default": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        model = LLMModelConfig.objects.get(pk=response.data["id"])
        self.assertEqual(model.usage, "vision_analyzer")
        self.assertEqual(model.protocol, "openai_responses")

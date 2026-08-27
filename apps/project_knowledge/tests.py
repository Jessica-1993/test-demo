from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.configuration.models import ProjectConfig
from apps.project_knowledge.models import KnowledgeExtractionRun, ProjectModule


class ProjectModuleRevisionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="module-admin", password="password")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = ProjectConfig.objects.create(name="模块项目", code="module-project")

    def create_module(self, code, name, parent=None, sort_order=0):
        response = self.client.post(
            reverse("project-module-list"),
            {
                "project": self.project.id,
                "parent": parent.id if parent else None,
                "code": code,
                "name": name,
                "description": "",
                "status": "active",
                "sort_order": sort_order,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return ProjectModule.objects.get(pk=response.data["id"])

    def test_create_tree_edit_and_confirm_keep_stable_entity(self):
        root = self.create_module("root", "根模块", sort_order=1)
        child = self.create_module("child", "子模块", parent=root, sort_order=2)
        self.assertEqual(root.revisions.get().status, "confirmed")

        edited = self.client.patch(
            reverse("project-module-detail", args=[child.id]),
            {"name": "待确认子模块", "sort_order": 3},
            format="json",
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        child.refresh_from_db()
        self.assertEqual(child.name, "子模块")
        self.assertEqual(edited.data["pending_revision"]["name"], "待确认子模块")

        tree = self.client.get(reverse("project-module-tree"), {"project": self.project.id})
        self.assertEqual(tree.status_code, status.HTTP_200_OK)
        self.assertEqual(tree.data[0]["id"], root.id)
        self.assertEqual(tree.data[0]["children"][0]["id"], child.id)
        self.assertEqual(tree.data[0]["children"][0]["path"], "根模块 / 子模块")

        confirmed = self.client.post(reverse("project-module-confirm", args=[child.id]))
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        child.refresh_from_db()
        self.assertEqual(child.name, "待确认子模块")
        self.assertEqual(child.parent_id, root.id)
        self.assertEqual(child.revisions.get(status="confirmed").revision_no, 2)
        self.assertEqual(self.client.post(reverse("project-module-confirm", args=[child.id])).status_code, status.HTTP_200_OK)

    def test_rejects_cycles_active_children_and_duplicate_code_on_confirm(self):
        root = self.create_module("root", "根模块")
        child = self.create_module("child", "子模块", parent=root)
        cycle = self.client.patch(
            reverse("project-module-detail", args=[root.id]),
            {"parent": child.id}, format="json",
        )
        self.assertEqual(cycle.status_code, status.HTTP_400_BAD_REQUEST)
        inactive = self.client.patch(
            reverse("project-module-detail", args=[root.id]),
            {"status": "inactive"}, format="json",
        )
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)

        duplicate = self.client.patch(
            reverse("project-module-detail", args=[child.id]),
            {"code": "root"}, format="json",
        )
        self.assertEqual(duplicate.status_code, status.HTTP_200_OK)
        rejected = self.client.post(reverse("project-module-confirm", args=[child.id]))
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        child.refresh_from_db()
        self.assertEqual(child.code, "child")

    def test_rejects_cross_project_parent(self):
        root = self.create_module("root", "根模块")
        other_project = ProjectConfig.objects.create(name="其他项目", code="other-project")
        other = ProjectModule.objects.create(project=other_project, code="other", name="其他")
        response = self.client.patch(
            reverse("project-module-detail", args=[root.id]),
            {"parent": other.id}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_duplicate_name_under_same_parent(self):
        root = self.create_module("root", "根模块")
        self.create_module("child-a", "登录", parent=root)

        response = self.client.post(
            reverse("project-module-list"),
            {
                "project": self.project.id,
                "parent": root.id,
                "code": "child-b",
                "name": "登录",
                "description": "",
                "status": "active",
                "sort_order": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class KnowledgeExtractionRetryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="knowledge-admin", password="password")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = ProjectConfig.objects.create(name="知识项目", code="knowledge-project")

    @patch("apps.project_knowledge.tasks.run_knowledge_extraction.delay")
    def test_failed_run_retry_creates_new_record(self, mocked_delay):
        source = KnowledgeExtractionRun.objects.create(
            project=self.project,
            source_document_ids=[11, 12],
            include_confirmed_requirements=True,
            status="failed",
            error_message="模型服务当前繁忙",
            created_by=self.user,
        )

        response = self.client.post(reverse("knowledge-extraction-run-retry", args=[source.id]), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        retry_run = KnowledgeExtractionRun.objects.get(pk=response.data["id"])
        self.assertEqual(retry_run.retry_of_id, source.id)
        self.assertEqual(retry_run.source_document_ids, [11, 12])
        mocked_delay.assert_called_once_with(retry_run.id)

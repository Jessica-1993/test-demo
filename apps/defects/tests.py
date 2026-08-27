from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.configuration.models import ProjectConfig
from apps.project_knowledge.models import ProjectModule

from .models import Defect


User = get_user_model()


class DefectApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="defect-user", password="password")
        self.client.force_authenticate(self.user)
        self.project = ProjectConfig.objects.create(name="缺陷项目", code="defect-project")
        self.other_project = ProjectConfig.objects.create(name="其他项目", code="other-defect-project")
        self.module = ProjectModule.objects.create(project=self.project, code="auth", name="认证")
        self.other_module = ProjectModule.objects.create(project=self.other_project, code="other", name="其他")

    def test_create_is_draft_and_confirm_enqueues_index(self):
        created = self.client.post(reverse("defect-list"), {
            "project": self.project.id,
            "defect_no": "BUG-001",
            "title": "登录失败",
            "severity": "high",
            "modules": [self.module.id],
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["knowledge_status"], "draft")

        with patch("apps.defects.views.SearchIndexService.enqueue") as enqueue:
            confirmed = self.client.post(reverse("defect-confirm"), {"ids": [created.data["id"]]}, format="json")
        self.assertEqual(confirmed.status_code, 200)
        defect = Defect.objects.get(pk=created.data["id"])
        self.assertEqual(defect.knowledge_status, "confirmed")
        self.assertEqual(defect.confirmed_by, self.user)
        enqueue.assert_called_once()

    def test_rejects_cross_project_module(self):
        response = self.client.post(reverse("defect-list"), {
            "project": self.project.id,
            "defect_no": "BUG-002",
            "title": "跨项目模块",
            "modules": [self.other_module.id],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("modules", response.data)

    def test_csv_import_creates_draft_and_reports_invalid_row(self):
        content = "缺陷编号,缺陷标题,严重程度,模块编码\nBUG-003,登录超时,严重,auth\n,缺少编号,一般,auth\n".encode("utf-8-sig")
        uploaded = SimpleUploadedFile("defects.csv", content, content_type="text/csv")
        response = self.client.post(reverse("defect-import"), {"project": self.project.id, "file": uploaded})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["success_count"], 1)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertTrue(Defect.objects.filter(project=self.project, defect_no="BUG-003", knowledge_status="draft").exists())

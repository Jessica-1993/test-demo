from django.conf import settings
from django.db import models

from apps.configuration.models import ProjectConfig


class SearchIndexJob(models.Model):
    ACTION_CHOICES = [("upsert", "写入"), ("delete", "删除"), ("rebuild", "重建")]
    STATUS_CHOICES = [("pending", "等待中"), ("running", "执行中"), ("success", "成功"), ("failed", "失败")]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="search_index_jobs", verbose_name="项目")
    asset_type = models.CharField(max_length=40, verbose_name="资产类型")
    asset_id = models.PositiveBigIntegerField(verbose_name="资产ID")
    revision_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="修订ID")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="upsert", verbose_name="动作")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    content_hash = models.CharField(max_length=64, blank=True, verbose_name="内容哈希")
    target_index = models.CharField(max_length=160, blank=True, verbose_name="目标索引")
    attempt_count = models.PositiveIntegerField(default=0, verbose_name="尝试次数")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_info = models.JSONField(default=dict, blank=True, verbose_name="结构化错误")
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries", verbose_name="重试来源")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="requested_search_jobs", verbose_name="发起人")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "search_index_jobs"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"], name="search_job_status_idx")]

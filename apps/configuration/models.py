from django.conf import settings
from django.db import models, transaction

from .catalog import ROLE_TYPE_CHOICES as CATALOG_ROLE_TYPE_CHOICES
from .catalog import USAGE_CHOICES as CATALOG_USAGE_CHOICES


class ProjectConfig(models.Model):
    STATUS_CHOICES = [
        ("active", "启用"),
        ("inactive", "停用"),
    ]

    name = models.CharField(max_length=120, verbose_name="项目名称")
    code = models.SlugField(max_length=80, unique=True, verbose_name="项目编码")
    description = models.TextField(blank=True, verbose_name="项目描述")
    owner = models.CharField(max_length=80, blank=True, verbose_name="负责人")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态")
    is_default = models.BooleanField(default=False, verbose_name="默认项目")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "configuration_project_configs"
        verbose_name = "项目配置"
        verbose_name_plural = "项目配置"
        ordering = ["-is_default", "-updated_at"]

    def __str__(self):
        return self.name

    def set_as_default(self):
        with transaction.atomic():
            ProjectConfig.objects.exclude(pk=self.pk).update(is_default=False)
            self.is_default = True
            self.save(update_fields=["is_default", "updated_at"])


class ProjectConfigRevision(models.Model):
    STATUS_CHOICES = [
        ("candidate", "待确认"),
        ("confirmed", "已确认"),
        ("superseded", "已替代"),
    ]

    project = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="revisions", verbose_name="项目")
    revision_no = models.PositiveIntegerField(verbose_name="修订号")
    name = models.CharField(max_length=120, verbose_name="项目名称")
    code = models.SlugField(max_length=80, verbose_name="项目编码")
    description = models.TextField(blank=True, verbose_name="项目描述")
    owner = models.CharField(max_length=80, blank=True, verbose_name="负责人")
    project_status = models.CharField(max_length=20, choices=ProjectConfig.STATUS_CHOICES, default="active", verbose_name="项目状态")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="candidate", verbose_name="修订状态")
    previous_revision = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="next_revisions", verbose_name="前一修订")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_project_config_revisions", verbose_name="创建人")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_project_config_revisions", verbose_name="确认人")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "configuration_project_config_revisions"
        ordering = ["-revision_no", "-id"]
        constraints = [models.UniqueConstraint(fields=["project", "revision_no"], name="uniq_project_config_revision_no")]


class LLMModelConfig(models.Model):
    PROVIDER_CHOICES = [
        ("chatgpt", "ChatGPT"),
        ("deepseek", "DeepSeek"),
        ("gemini", "Gemini"),
        ("qwen", "千问"),
    ]

    PROTOCOL_CHOICES = [
        ("openai_compatible", "OpenAI Compatible"),
        ("openai_responses", "OpenAI Responses"),
        ("gemini", "Gemini"),
    ]

    USAGE_CHOICES = CATALOG_USAGE_CHOICES

    name = models.CharField(max_length=120, verbose_name="配置名称")
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, verbose_name="供应商")
    protocol = models.CharField(max_length=40, choices=PROTOCOL_CHOICES, default="openai_compatible", verbose_name="协议类型")
    usage = models.CharField(max_length=40, choices=USAGE_CHOICES, default="general_chat", verbose_name="用途")
    model_name = models.CharField(max_length=120, verbose_name="模型名称")
    base_url = models.URLField(max_length=500, blank=True, verbose_name="Base URL")
    api_key = models.CharField(max_length=800, verbose_name="API Key")
    max_tokens = models.PositiveIntegerField(default=4096, verbose_name="最大输出 Token")
    temperature = models.FloatField(default=0.7, verbose_name="Temperature")
    top_p = models.FloatField(default=1.0, verbose_name="Top P")
    embedding_dimension = models.PositiveIntegerField(default=768, verbose_name="向量维度")
    is_active = models.BooleanField(default=True, verbose_name="启用")
    is_default = models.BooleanField(default=False, verbose_name="默认模型")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "configuration_llm_model_configs"
        verbose_name = "大模型配置"
        verbose_name_plural = "大模型配置"
        ordering = ["usage", "-is_default", "-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.model_name})"

    def set_as_default(self):
        with transaction.atomic():
            LLMModelConfig.objects.filter(usage=self.usage).exclude(pk=self.pk).update(is_default=False)
            self.is_default = True
            self.is_active = True
            self.save(update_fields=["is_default", "is_active", "updated_at"])


class PromptConfig(models.Model):
    ROLE_TYPE_CHOICES = CATALOG_ROLE_TYPE_CHOICES

    name = models.CharField(max_length=120, verbose_name="配置名称")
    role_type = models.CharField(max_length=40, choices=ROLE_TYPE_CHOICES, verbose_name="系统角色类型")
    prompt_content = models.TextField(verbose_name="提示词内容")
    llm_model = models.ForeignKey(
        LLMModelConfig,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="system_roles",
        verbose_name="绑定大模型",
    )
    is_active = models.BooleanField(default=True, verbose_name="启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "configuration_prompt_configs"
        verbose_name = "系统角色配置"
        verbose_name_plural = "系统角色配置"
        ordering = ["role_type", "-is_active", "-updated_at"]

    def __str__(self):
        return f"{self.get_role_type_display()} - {self.name}"

    def activate(self):
        with transaction.atomic():
            PromptConfig.objects.filter(role_type=self.role_type).exclude(pk=self.pk).update(is_active=False)
            self.is_active = True
            self.save(update_fields=["is_active", "updated_at"])

    @classmethod
    def get_active_config(cls, role_type):
        return cls.objects.select_related("llm_model").filter(role_type=role_type, is_active=True).first()

    @classmethod
    def resolve_active(cls, role_type, error_class=RuntimeError):
        role = cls.get_active_config(role_type)
        if not role:
            raise error_class(f"缺少启用的系统角色: {dict(cls.ROLE_TYPE_CHOICES).get(role_type, role_type)}")
        if not role.llm_model:
            raise error_class(f"系统角色未绑定大模型: {role.get_role_type_display()}")
        if not role.llm_model.is_active:
            raise error_class(f"系统角色绑定的大模型已停用: {role.get_role_type_display()}")
        if role.llm_model.usage != role.role_type:
            raise error_class(f"系统角色与大模型用途不匹配: {role.get_role_type_display()}")
        return role

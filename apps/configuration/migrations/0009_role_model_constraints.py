from django.db import migrations, models


ROLE_TYPES = [
    ("general_chat", "通用对话助手"),
    ("requirement_integrator", "需求整合专家"),
    ("testcase_writer", "测试用例生成专家"),
    ("testcase_reviewer", "测试用例评审专家"),
    ("vision_analyzer", "图片理解专家"),
    ("embedding", "文本向量角色"),
    ("automation_agent", "自动化执行 Agent"),
]

USAGES = [
    ("general_chat", "通用对话"),
    ("requirement_integrator", "需求整合"),
    ("testcase_writer", "用例生成"),
    ("testcase_reviewer", "用例评审"),
    ("vision_analyzer", "图片理解"),
    ("embedding", "文本向量"),
    ("automation_agent", "自动化 Agent"),
]

DEFAULT_PROMPTS = {
    "general_chat": "你是 TestHub 的通用测试协作助手。请基于事实提供明确、可验证的结论，不得补充材料中不存在的业务规则。",
    "requirement_integrator": "你是一名资深需求分析与测试设计专家。请忠实整合原始材料与可信证据，保留冲突和不确定项，不得臆测。",
    "testcase_writer": "你是一位资深测试用例编写专家。请生成完整、独立、可执行并覆盖正常、异常和边界场景的测试用例。",
    "testcase_reviewer": "你是一名资深测试评审专家。请严格检查用例覆盖率、逻辑性、可执行性和描述规范。",
    "vision_analyzer": "你是一名面向软件测试的图片理解专家。请只提取图片中可验证的信息，不得臆测未展示内容。",
    "embedding": "",
    "automation_agent": "你是一名测试自动化执行 Agent。请规划可审计、可恢复的操作并使用明确断言，不得执行未授权的破坏性操作。",
}

USAGE_PROTOCOLS = {
    "general_chat": {"openai_compatible", "gemini"},
    "requirement_integrator": {"openai_compatible", "gemini"},
    "testcase_writer": {"openai_compatible", "gemini"},
    "testcase_reviewer": {"openai_compatible", "gemini"},
    "vision_analyzer": {"openai_responses", "gemini"},
    "embedding": {"gemini"},
    "automation_agent": {"openai_compatible", "gemini"},
}


def _active_model(model_config, usage):
    return (
        model_config.objects.filter(usage=usage, is_active=True, is_default=True).first()
        or model_config.objects.filter(usage=usage, is_active=True).order_by("-updated_at", "-id").first()
    )


def _copy_model_for_usage(model_config, source, usage):
    existing = (
        model_config.objects.filter(
            usage=usage,
            provider=source.provider,
            protocol=source.protocol,
            model_name=source.model_name,
            base_url=source.base_url,
        )
        .order_by("-is_active", "-is_default", "-updated_at", "-id")
        .first()
    )
    if existing:
        return existing
    has_default = model_config.objects.filter(usage=usage, is_default=True).exists()
    return model_config.objects.create(
        name=f"{source.name}-{dict(USAGES)[usage]}"[:120],
        provider=source.provider,
        protocol=source.protocol,
        usage=usage,
        model_name=source.model_name,
        base_url=source.base_url,
        api_key=source.api_key,
        max_tokens=source.max_tokens,
        temperature=source.temperature,
        top_p=source.top_p,
        embedding_dimension=source.embedding_dimension,
        is_active=source.is_active,
        is_default=source.is_active and not has_default,
    )


def align_roles_and_models(apps, _schema_editor):
    model_config = apps.get_model("configuration", "LLMModelConfig")
    prompt_config = apps.get_model("configuration", "PromptConfig")

    for role in prompt_config.objects.exclude(llm_model_id=None).select_related("llm_model"):
        if role.llm_model.usage != role.role_type:
            if role.llm_model.protocol in USAGE_PROTOCOLS[role.role_type]:
                role.llm_model = _copy_model_for_usage(model_config, role.llm_model, role.role_type)
                role.save(update_fields=["llm_model", "updated_at"])
            else:
                role.llm_model = _active_model(model_config, role.role_type)
                role.is_active = bool(role.llm_model)
                role.save(update_fields=["llm_model", "is_active", "updated_at"])

    for role_type, label in ROLE_TYPES:
        roles = prompt_config.objects.filter(role_type=role_type).order_by("-is_active", "-updated_at", "-id")
        if not roles.exists():
            model = _active_model(model_config, role_type)
            prompt_config.objects.create(
                name=f"默认{label}",
                role_type=role_type,
                prompt_content=DEFAULT_PROMPTS[role_type],
                llm_model=model,
                is_active=bool(model),
            )
            continue

        active_kept = False
        for role in roles:
            model = role.llm_model
            if (not model or not model.is_active or model.usage != role_type) and role.is_active:
                replacement = _active_model(model_config, role_type)
                role.llm_model = replacement
                role.is_active = bool(replacement) and not active_kept
                role.save(update_fields=["llm_model", "is_active", "updated_at"])
            elif role.is_active and active_kept:
                role.is_active = False
                role.save(update_fields=["is_active", "updated_at"])
            if role.is_active:
                active_kept = True


class Migration(migrations.Migration):

    dependencies = [
        ("configuration", "0008_llmmodelconfig_embedding_dimension_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmmodelconfig",
            name="usage",
            field=models.CharField(choices=USAGES, default="general_chat", max_length=40, verbose_name="用途"),
        ),
        migrations.AlterField(
            model_name="promptconfig",
            name="role_type",
            field=models.CharField(choices=ROLE_TYPES, max_length=40, verbose_name="系统角色类型"),
        ),
        migrations.RunPython(align_roles_and_models, migrations.RunPython.noop),
    ]

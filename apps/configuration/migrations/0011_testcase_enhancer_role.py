from django.db import migrations, models


USAGE_CHOICES = [
    ("general_chat", "通用对话"),
    ("requirement_integrator", "需求整合"),
    ("testcase_writer", "用例生成"),
    ("testcase_enhancer", "用例增强"),
    ("testcase_reviewer", "用例评审"),
    ("vision_analyzer", "图片理解"),
    ("embedding", "文本向量"),
    ("automation_agent", "自动化 Agent"),
]

ROLE_CHOICES = [
    ("general_chat", "通用对话助手"),
    ("requirement_integrator", "需求整合专家"),
    ("testcase_writer", "测试用例生成专家"),
    ("testcase_enhancer", "测试用例增强专家"),
    ("testcase_reviewer", "测试用例评审专家"),
    ("vision_analyzer", "图片理解专家"),
    ("embedding", "文本向量角色"),
    ("automation_agent", "自动化执行 Agent"),
]

DEFAULT_PROMPT = (
    "你是一名资深测试用例增强专家。请以当前正式需求和当前版本用例为基线，"
    "结合可信历史用例与缺陷证据识别覆盖缺口。只能提出新增或优化建议，不得删除用例；"
    "每条建议必须引用给定证据，或明确标记为仅由当前需求推导，并严格输出任务要求的 JSON。"
)


def seed_enhancer_role(apps, schema_editor):
    PromptConfig = apps.get_model("configuration", "PromptConfig")
    PromptConfig.objects.get_or_create(
        role_type="testcase_enhancer",
        defaults={
            "name": "默认测试用例增强专家",
            "prompt_content": DEFAULT_PROMPT,
            "is_active": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("configuration", "0010_projectconfigrevision_and_more")]
    operations = [
        migrations.AlterField(
            model_name="llmmodelconfig",
            name="usage",
            field=models.CharField(choices=USAGE_CHOICES, default="general_chat", max_length=40, verbose_name="用途"),
        ),
        migrations.AlterField(
            model_name="promptconfig",
            name="role_type",
            field=models.CharField(choices=ROLE_CHOICES, max_length=40, verbose_name="系统角色类型"),
        ),
        migrations.RunPython(seed_enhancer_role, migrations.RunPython.noop),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configuration", "0006_llm_openai_responses_vision_usage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmmodelconfig",
            name="usage",
            field=models.CharField(
                choices=[
                    ("general_chat", "通用对话"),
                    ("requirement_integrator", "需求整合"),
                    ("testcase_writer", "用例生成"),
                    ("testcase_reviewer", "用例评审"),
                    ("vision_analyzer", "图片理解"),
                    ("automation_agent", "自动化 Agent"),
                ],
                default="general_chat",
                max_length=40,
                verbose_name="用途",
            ),
        ),
        migrations.AlterField(
            model_name="promptconfig",
            name="role_type",
            field=models.CharField(
                choices=[
                    ("requirement_integrator", "需求整合专家"),
                    ("testcase_writer", "测试用例生成专家"),
                    ("testcase_reviewer", "测试用例评审专家"),
                ],
                max_length=40,
                verbose_name="系统角色类型",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configuration", "0005_promptconfig_system_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmmodelconfig",
            name="protocol",
            field=models.CharField(
                choices=[
                    ("openai_compatible", "OpenAI Compatible"),
                    ("openai_responses", "OpenAI Responses"),
                    ("gemini", "Gemini"),
                ],
                default="openai_compatible",
                max_length=40,
                verbose_name="协议类型",
            ),
        ),
        migrations.AlterField(
            model_name="llmmodelconfig",
            name="usage",
            field=models.CharField(
                choices=[
                    ("general_chat", "通用对话"),
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
    ]

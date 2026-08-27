from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RoleModelMigrationTests(TransactionTestCase):
    migrate_from = ("configuration", "0008_llmmodelconfig_embedding_dimension_and_more")
    migrate_to = ("configuration", "0009_role_model_constraints")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        model_config = old_apps.get_model("configuration", "LLMModelConfig")
        prompt_config = old_apps.get_model("configuration", "PromptConfig")
        prompt_config.objects.all().delete()
        model_config.objects.all().delete()

        general = model_config.objects.create(
            name="shared-gemini",
            provider="gemini",
            protocol="gemini",
            usage="general_chat",
            model_name="gemini-test",
            base_url="https://generativelanguage.googleapis.com",
            api_key="migration-secret",
            is_active=True,
            is_default=True,
        )
        vision = model_config.objects.create(
            name="vision",
            provider="chatgpt",
            protocol="openai_responses",
            usage="vision_analyzer",
            model_name="gpt-test",
            base_url="https://api.openai.com",
            api_key="vision-secret",
            is_active=True,
            is_default=True,
        )
        embedding = model_config.objects.create(
            name="embedding",
            provider="gemini",
            protocol="gemini",
            usage="embedding",
            model_name="gemini-embedding-2",
            base_url="https://generativelanguage.googleapis.com",
            api_key="embedding-secret",
            is_active=True,
            is_default=True,
        )
        prompt_config.objects.create(
            name="integrator",
            role_type="requirement_integrator",
            prompt_content="整合",
            llm_model=general,
            is_active=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps
        self.general_id = general.id
        self.vision_id = vision.id
        self.embedding_id = embedding.id

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_clones_mismatched_model_and_seeds_roles(self):
        model_config = self.apps.get_model("configuration", "LLMModelConfig")
        prompt_config = self.apps.get_model("configuration", "PromptConfig")

        general = model_config.objects.get(pk=self.general_id)
        integrator = prompt_config.objects.get(role_type="requirement_integrator")
        self.assertEqual(general.usage, "general_chat")
        self.assertNotEqual(integrator.llm_model_id, general.id)
        self.assertEqual(integrator.llm_model.usage, "requirement_integrator")
        self.assertEqual(integrator.llm_model.api_key, "migration-secret")
        self.assertEqual(prompt_config.objects.get(role_type="vision_analyzer").llm_model_id, self.vision_id)
        self.assertEqual(prompt_config.objects.get(role_type="embedding").llm_model_id, self.embedding_id)
        self.assertFalse(prompt_config.objects.get(role_type="automation_agent").is_active)
        self.assertEqual(set(prompt_config.objects.values_list("role_type", flat=True)), {
            "general_chat",
            "requirement_integrator",
            "testcase_writer",
            "testcase_reviewer",
            "vision_analyzer",
            "embedding",
            "automation_agent",
        })

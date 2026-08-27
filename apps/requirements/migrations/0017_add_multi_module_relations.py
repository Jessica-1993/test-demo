from django.db import migrations, models


def backfill_multi_modules(apps, schema_editor):
    RequirementItem = apps.get_model("requirements", "RequirementItem")
    RequirementIntegrationDraft = apps.get_model("requirements", "RequirementIntegrationDraft")
    RequirementFamily = apps.get_model("requirements", "RequirementFamily")
    RequirementRevision = apps.get_model("requirements", "RequirementRevision")

    for item in RequirementItem.objects.all().iterator():
        labels = [item.module.strip()] if item.module and item.module.strip() else []
        RequirementItem.objects.filter(pk=item.pk).update(source_module_labels=labels)
        if item.formal_module_id:
            item.formal_modules.add(item.formal_module_id)
    for draft in RequirementIntegrationDraft.objects.all().iterator():
        if draft.formal_module_id:
            draft.formal_modules.add(draft.formal_module_id)
            RequirementIntegrationDraft.objects.filter(pk=draft.pk).update(module_resolution_status="resolved")
    for family in RequirementFamily.objects.all().iterator():
        if family.module_id:
            family.modules.add(family.module_id)
    for revision in RequirementRevision.objects.all().iterator():
        if revision.module_id:
            revision.modules.add(revision.module_id)


class Migration(migrations.Migration):
    dependencies = [
        ("project_knowledge", "0002_projectmodulerevision_and_more"),
        ("requirements", "0016_restore_draft_requirement_versions"),
    ]
    operations = [
        migrations.AddField(
            model_name="requirementitem",
            name="source_module_labels",
            field=models.JSONField(blank=True, default=list, verbose_name="原始模块标签"),
        ),
        migrations.AddField(
            model_name="requirementitem",
            name="formal_modules",
            field=models.ManyToManyField(blank=True, related_name="requirement_items", to="project_knowledge.projectmodule", verbose_name="正式模块"),
        ),
        migrations.AddField(
            model_name="requirementintegrationdraft",
            name="formal_modules",
            field=models.ManyToManyField(blank=True, related_name="integration_drafts", to="project_knowledge.projectmodule", verbose_name="正式模块"),
        ),
        migrations.AddField(
            model_name="requirementintegrationdraft",
            name="suggested_module_paths",
            field=models.JSONField(blank=True, default=list, verbose_name="建议模块路径"),
        ),
        migrations.AddField(
            model_name="requirementintegrationdraft",
            name="unresolved_module_paths",
            field=models.JSONField(blank=True, default=list, verbose_name="未解决模块路径"),
        ),
        migrations.AddField(
            model_name="requirementintegrationdraft",
            name="module_resolution_status",
            field=models.CharField(choices=[("resolved", "已解决"), ("needs_review", "待人工处理")], default="needs_review", max_length=20, verbose_name="模块归属状态"),
        ),
        migrations.AddField(
            model_name="requirementfamily",
            name="modules",
            field=models.ManyToManyField(related_name="requirement_families", to="project_knowledge.projectmodule", verbose_name="正式模块"),
        ),
        migrations.AddField(
            model_name="requirementrevision",
            name="modules",
            field=models.ManyToManyField(related_name="requirement_revisions", to="project_knowledge.projectmodule", verbose_name="正式模块"),
        ),
        migrations.RunPython(backfill_multi_modules, migrations.RunPython.noop),
    ]

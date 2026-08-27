import re

from django.db import migrations


PREFIX_PATTERN = re.compile(
    r"^\s*(?:第?[一二三四五六七八九十百0-9]+[章节部分]|\d+(?:[.．]\d+)*)[、.．：:\s]+"
)


def clean_heading(value):
    cleaned = PREFIX_PATTERN.sub("", (value or "").strip()).strip()
    return cleaned or (value or "").strip()


def clean_existing_requirements(apps, schema_editor):
    RequirementDocument = apps.get_model("requirements", "RequirementDocument")
    RequirementItem = apps.get_model("requirements", "RequirementItem")
    for document in RequirementDocument.objects.all().iterator():
        title = clean_heading(document.title)
        if title != document.title:
            document.title = title
            document.save(update_fields=["title"])
    for item in RequirementItem.objects.all().iterator():
        item.title = clean_heading(item.title)
        item.module = clean_heading(item.module)
        item.supplementary_description = "\n".join(
            clean_heading(line) for line in item.supplementary_description.splitlines()
        )
        item.save(update_fields=["title", "module", "supplementary_description"])


class Migration(migrations.Migration):
    dependencies = [("requirements", "0007_remove_requirementitem_source_excerpt_and_more")]

    operations = [migrations.RunPython(clean_existing_requirements, migrations.RunPython.noop)]

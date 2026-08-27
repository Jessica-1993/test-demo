import re

from django.db import migrations


PREFIX_PATTERN = re.compile(r"^\s*REQ[-_]\d+[、.．：:\s]+", re.IGNORECASE)


def clean_requirement_codes(apps, schema_editor):
    RequirementItem = apps.get_model("requirements", "RequirementItem")
    for item in RequirementItem.objects.all().iterator():
        title = PREFIX_PATTERN.sub("", item.title).strip()
        if title and title != item.title:
            item.title = title
            item.save(update_fields=["title"])


class Migration(migrations.Migration):
    dependencies = [("requirements", "0008_clean_requirement_heading_prefixes")]

    operations = [migrations.RunPython(clean_requirement_codes, migrations.RunPython.noop)]

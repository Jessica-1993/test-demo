from django.db import migrations


def normalize_qiniu_urls(apps, schema_editor):
    RequirementDocument = apps.get_model("requirements", "RequirementDocument")
    for document in RequirementDocument.objects.exclude(qiniu_url="").iterator():
        if not document.qiniu_url.startswith(("http://", "https://")):
            document.qiniu_url = f"https://{document.qiniu_url.lstrip('/')}"
            document.save(update_fields=["qiniu_url"])


class Migration(migrations.Migration):
    dependencies = [("requirements", "0005_requirementcontentblock_requirementparserun_and_more")]

    operations = [migrations.RunPython(normalize_qiniu_urls, migrations.RunPython.noop)]

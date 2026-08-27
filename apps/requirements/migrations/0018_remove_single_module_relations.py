from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("requirements", "0017_add_multi_module_relations")]
    operations = [
        migrations.RemoveField(model_name="requirementitem", name="formal_module"),
        migrations.RemoveField(model_name="requirementintegrationdraft", name="formal_module"),
        migrations.RemoveField(model_name="requirementfamily", name="module"),
        migrations.RemoveField(model_name="requirementrevision", name="module"),
    ]

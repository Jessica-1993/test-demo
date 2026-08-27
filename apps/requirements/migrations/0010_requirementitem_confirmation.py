from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("requirements", "0009_clean_requirement_code_prefixes"),
    ]

    operations = [
        migrations.AddField(
            model_name="requirementitem",
            name="confirm_status",
            field=models.CharField(
                choices=[("pending", "待确认"), ("confirmed", "已确认")],
                default="confirmed",
                max_length=20,
                verbose_name="确认状态",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="requirementitem",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="确认时间"),
        ),
        migrations.AddField(
            model_name="requirementitem",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="confirmed_requirement_items",
                to=settings.AUTH_USER_MODEL,
                verbose_name="确认人",
            ),
        ),
        migrations.AlterField(
            model_name="requirementitem",
            name="confirm_status",
            field=models.CharField(
                choices=[("pending", "待确认"), ("confirmed", "已确认")],
                default="pending",
                max_length=20,
                verbose_name="确认状态",
            ),
        ),
    ]

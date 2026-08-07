import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgcode_enterprise", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="orgcode",
            name="code",
            field=models.CharField(
                db_index=True,
                max_length=50,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="orgcode",
            name="discount_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="orgcode",
            name="discount_percent",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="orgcode",
            name="enterprise_customer_uuid",
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            model_name="orgcodeusage",
            name="code",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="usages",
                to="orgcode_enterprise.orgcode",
            ),
        ),
        migrations.AlterField(
            model_name="orgcodeusage",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="orgcode_usages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

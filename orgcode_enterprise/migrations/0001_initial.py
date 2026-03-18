from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OrgCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('enterprise_customer_uuid', models.UUIDField()),
                ('description', models.CharField(blank=True, max_length=255)),
                ('active', models.BooleanField(default=True)),
                ('discount_percent', models.PositiveIntegerField(blank=True, null=True)),
                ('discount_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('usage_limit', models.PositiveIntegerField(blank=True, null=True)),
                ('times_used', models.PositiveIntegerField(default=0)),
                ('max_uses_per_user', models.PositiveIntegerField(blank=True, null=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('course_id', models.CharField(blank=True, max_length=255, null=True)),
                ('program_id', models.CharField(blank=True, max_length=255, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='OrgCodeUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('times_used', models.PositiveIntegerField(default=0)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('code', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='orgcode_enterprise.orgcode')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'unique_together': {('user', 'code')},
            },
        ),
    ]

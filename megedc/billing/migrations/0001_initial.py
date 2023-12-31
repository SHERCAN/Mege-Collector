# Generated by Django 3.2.6 on 2021-08-18 02:02

from django.db import migrations, models
import django.db.models.deletion
import megedc.billing.invoice_id
import megedc.billing.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('general', '0008_auto_20210817_2134'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.JSONField(blank=True, default=dict, null=True)),
                ('invoice_id', models.CharField(default=megedc.billing.invoice_id.invoice_uuid_generator, max_length=128)),
                ('file', megedc.billing.models.InvoiceFileField(blank=True, null=True, upload_to=megedc.billing.models._invode_file_storage_path)),
                ('file_mime_type', models.CharField(blank=True, max_length=256, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('removed_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='Invoices', to='general.customer')),
            ],
        ),
    ]

# Generated by Django 3.2.9 on 2022-06-04 17:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0009_customer_is_invoice_header'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='invoice_id_generator_kwargs',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='tax_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='invoice_id_generator_kwargs',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='tax_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='client',
            name='invoice_id_generator',
            field=models.CharField(choices=[('UUID', 'UUID Generator'), ('AUTOINSCREMENT', 'Auto Increment')], default='UUID', help_text='Invoice id generator', max_length=20),
        ),
        migrations.AlterField(
            model_name='customer',
            name='invoice_id_generator',
            field=models.CharField(blank=True, choices=[('UUID', 'UUID Generator'), ('AUTOINSCREMENT', 'Auto Increment')], help_text='Invoice id generator', max_length=20, null=True),
        ),
    ]
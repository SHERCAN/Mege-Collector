# Generated by Django 3.2.9 on 2022-06-04 21:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0010_auto_20220604_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='unitcost',
            name='invoice_item_format',
            field=models.TextField(blank=True, null=True),
        ),
    ]

# Generated by Django 3.2 on 2021-07-24 14:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0005_rename_remove_at_project_removed_at'),
        ('x6gateapi', '0004_measure_data_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='measure',
            name='unit_cost',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='measures', to='general.unitcost'),
        ),
    ]

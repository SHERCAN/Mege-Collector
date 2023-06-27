# Generated by Django 3.2 on 2021-05-18 01:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('x6gateapi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrendLogData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_time', models.DateTimeField()),
                ('dblink', models.CharField(blank=True, max_length=128, null=True)),
                ('name', models.CharField(blank=True, max_length=128, null=True)),
                ('value', models.CharField(blank=True, max_length=128, null=True)),
                ('unit', models.CharField(blank=True, max_length=128, null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='trend_log_data', to='x6gateapi.device')),
            ],
        ),
        migrations.AddIndex(
            model_name='trendlogdata',
            index=models.Index(fields=['device', 'name', 'date_time'], name='x6gateapi_t_device__16755a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='trendlogdata',
            unique_together={('device', 'dblink', 'date_time')},
        ),
    ]
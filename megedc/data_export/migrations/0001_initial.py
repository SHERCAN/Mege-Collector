# Generated by Django 3.2 on 2021-04-11 16:18

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('x6gateapi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportDataProxyModel',
            fields=[
            ],
            options={
                'verbose_name': 'Export data',
                'verbose_name_plural': 'Export data',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('x6gateapi.rtdata',),
        ),
    ]

# Generated by Django 3.2 on 2021-04-11 16:18

from django.db import migrations, models
import django.db.models.deletion
import timezone_field.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Client name', max_length=128)),
                ('desc', models.TextField(help_text='Client description', null=True)),
                ('time_zone', timezone_field.fields.TimeZoneField(default='UTC', help_text='Client timezone')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Project name', max_length=128)),
                ('desc', models.TextField(help_text='Project description', null=True)),
                ('time_zone', timezone_field.fields.TimeZoneField(blank=True, help_text='Project timezone', null=True)),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='projects', to='general.client')),
            ],
        ),
    ]

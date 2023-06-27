from __future__ import absolute_import

import csv
import pytz
import tempfile
from celery import shared_task
from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.transaction import atomic
from megedc.emporiaenergy.partner_api import partner_api
from os.path import join


@shared_task
def emporia_energy_gateway_sync(gateways=None):
    queryset = apps.get_model('x6gateapi.gateway').objects.filter(
        enabled=True,
        removed_at__isnull=True,
        gateway_type='emporia_energy'
    )
    rtd_manager = apps.get_model('x6gateapi.rtdata').objects
    if gateways:
        queryset = queryset.filter(id__in=gateways)

    for gateway in queryset.iterator():
        extra_data = gateway.extra_data.get('emporia_energy', {})
        from_date = extra_data.get('from_date')
        if from_date is not None:
            from_date = datetime.fromisoformat(from_date)
        else:
            continue

        secret = gateway.secret_extra_data.get('emporia_energy', {})
        ee_api = partner_api(
            (secret.get('email'), secret.get('password')),
            host=secret.get('host'),
            port=secret.get('port')
        )
        new_from_date = datetime.now()
        u_data = ee_api.get_usage_data(
            int(from_date.strftime('%s')),
            int(new_from_date.strftime('%s')),
            extra_data.get('resolution'),
            all_channels=True,
            devices=[gateway.sn]
        )

        if not u_data or u_data[0].manufacturer_device_id != gateway.sn:
            continue

        usage_data = u_data[0]

        with atomic():
            for channel_usage in usage_data.channel_usage:
                existe_channel = gateway.devices.filter(
                    removed_at__isnull=True,
                    channel=channel_usage.channel,
                    gateway=gateway
                ).exists()
                if not existe_channel:
                    continue
                device = gateway.devices.filter(
                    removed_at__isnull=True,
                    channel=str(channel_usage.channel),
                    gateway=gateway
                ).get()
                timezone = str(device.gateway.timezone)
                for i in range(len(usage_data.bucket_epoch_seconds)):
                    date_time = pytz.timezone(timezone).localize(
                        datetime.fromtimestamp(
                            usage_data.bucket_epoch_seconds[i]
                        )
                    )
                    rt_data, created = rtd_manager.get_or_create(
                        date_time=date_time,
                        gateway=gateway,
                        defaults={
                            'discard': False,
                            'logdt': date_time.strftime('%Y-%m-%d %H:%M:%S'),
                        }
                    )
                    rtd_manager.filter(id=rt_data.id).update(
                        date_time=date_time
                    )
                    rt_data.nodes.get_or_create(
                        device=device,
                        data=rt_data,
                        name='Watt',
                        defaults={
                            'value': str(channel_usage.usage[i]),
                            'unit': 'Watt',
                        }
                    )
        extra_data['from_date'] = new_from_date.isoformat()
        gateway.extra_data['emporia_energy'] = extra_data
        gateway.save()


@shared_task
def mmg_errors_alert(*args, **kwargs):
    csv_data = []
    queryset = apps.get_model('x6gateapi.RTAlarm').objects.filter(
        type='MMG_GET_VALUE_ERROR',
        flag='M',
    )
    if queryset.exists():
        for alarm in queryset.iterator():
            row_data = {
                'logdt': alarm.logdt,
                'name': alarm.name,
                'value': alarm.value,
                'device_id': alarm.device.id,
                'device_channel': alarm.device.channel,
                'device_name': alarm.device.name,
                'device_desc': alarm.device.desc,
                'gateway_type': alarm.device.gateway.gateway_type,
                'gateway_sn': alarm.device.gateway.sn,
                'gateway_name': alarm.device.gateway.name,
                'project_uuid': alarm.device.gateway.project.uuid,
                'project_name': alarm.device.gateway.project.name,
                'client_name': alarm.device.gateway.project.client.name,
            }
            csv_data.append(row_data)
        with tempfile.TemporaryDirectory() as tmpdirname:
            file_path = join(tmpdirname, 'alarms.csv')
            with open(file_path, 'w') as csvfile:
                fieldnames = [
                    'logdt',
                    'name',
                    'value',
                    'device_id',
                    'device_channel',
                    'device_name',
                    'device_desc',
                    'gateway_type',
                    'gateway_sn',
                    'gateway_name',
                    'project_uuid',
                    'project_name',
                    'client_name',
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in csv_data:
                    writer.writerow(row)
            email = EmailMessage(
                'MEGE DC ALARMAS MODBUS GATEWAYS',
                'Adjunto archivo cvs con las últimas alarmas',
                settings.DEFAULT_FROM_EMAIL,
                args,
                []
            )
            email.attach_file(file_path)
            email.send()
        queryset.update(flag='P')

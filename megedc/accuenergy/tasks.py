from __future__ import absolute_import

import pytz
from .api_client import AccuenergyApiClient
from celery import shared_task, Task
from datetime import datetime
from django.apps import apps


ACCUENERGY_ALARM_DEV = 'ALARMS'


class AccuenergyAlarmsUpdater(Task):

    client_class = AccuenergyApiClient

    @property
    def gateway_manager(self):
        return apps.get_model('x6gateapi.Gateway').objects

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.Device').objects

    def _gateway_iter(self):
        return self.gateway_manager.filter(
            enabled=True,
            removed_at__isnull=True,
            gateway_type__startswith='AcuRev',
            secret_extra_data__api_client__token__isnull=False,
            extra_data__alarms_enabled=True,
        ).iterator()

    def main(self):
        res = {}
        for gateway in self._gateway_iter():
            result = {}
            try:
                ret = self._proc_gateway(gateway)
                if ret is None:
                    continue
                result['result'] = ret
            except Exception as exce:
                result['exception'] = str(exce)
                raise exce
            res[gateway.id] = result
        return res

    def _proc_gateway(self, gateway):
        client_data = gateway.secret_extra_data.get('api_client')
        api_client = self.client_class(
            client_data['remote_access_url'], client_data['token']
        )
        gw_alarms = api_client.get_readings_alarm()
        rets = []
        for gw_alarm in gw_alarms:
            try:
                ret = self._proc_alarm(gateway, gw_alarm)
                if ret is not None:
                    rets.append({
                        'data': ret,
                        'alarm': gw_alarm
                    })
            except Exception as exce:
                rets.append({
                    'errors': str(exce),
                    'alarm': gw_alarm
                })
                raise exce
        return rets

    def _proc_alarm(self, gateway, alarm):
        device, created = self.device_manager.get_or_create(
            id=ACCUENERGY_ALARM_DEV,
            channel=alarm['Alarm ID'],
            gateway=gateway,
            defaults={
                'name': 'Alarm channel %s' % (alarm['Alarm ID']),
                'ready': True,

            }
        )
        rt_alarm, created = device.alarms.get_or_create(
            device=device,
            logdt=alarm['Timestamp'],
            defaults={
                'type': alarm['Status'],
                'name': alarm['Alarm Channel'],
                'value': alarm['Value'],
            }
        )
        if created:
            rt_alarm.date_time = pytz.timezone(
                str(gateway.timezone)
            ).localize(datetime.fromisoformat(alarm['Timestamp']))
            rt_alarm.save()
            alerts = device.gateway.alerts.filter(
                enabled=True,
                device_channel=device.channel,
                device_id=device.id,
                gateway=gateway,
                removed_at__isnull=True,
            )
            for alert in alerts.iterator():
                alert.send(rt_alarm)
            return True


@shared_task(base=AccuenergyAlarmsUpdater, bind=True)
def update_accuenergy_alarms(self):
    return self.main()

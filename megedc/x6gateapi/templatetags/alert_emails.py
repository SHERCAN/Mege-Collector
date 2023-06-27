from django import template
from django.core.exceptions import ObjectDoesNotExist
from megedc.accuenergy.tasks import ACCUENERGY_ALARM_DEV


register = template.Library()


@register.filter(name='mult')
def mult(value, num):
    return value * num


@register.filter()
def time_diff_last_alarm(alarm, channel):
    device = None
    try:
        device = alarm.device.gateway.devices.get(
            id=ACCUENERGY_ALARM_DEV,
            channel=str(channel),
        )
    except ObjectDoesNotExist:
        pass
    if device is None:
        return 0
    other_alarm = device.alarms.filter(
        removed_at__isnull=True,
        date_time__lte=alarm.date_time
    ).order_by('-date_time').first()
    if other_alarm is None:
        return 0
    diff = alarm.date_time - other_alarm.date_time
    return diff.total_seconds()

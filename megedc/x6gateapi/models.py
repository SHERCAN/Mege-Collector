import re
from .emails import send_alert
from datetime import datetime
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.template import Template, Context
from megedc.billing.measue_calculators import Calculators
from megedc.general.models import Project, Local, UnitCost
from timezone_field import TimeZoneField
from tinymce.models import HTMLField


class Gateway(models.Model):

    gateway_type = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    sn = models.CharField(
        max_length=128
    )

    name = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    ver = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    site = models.JSONField()

    owner = models.JSONField()

    room = models.JSONField()

    extra_data = models.JSONField(default=dict, null=True, blank=True)

    secret_extra_data = models.JSONField(default=dict, null=True, blank=True)

    time_zone = TimeZoneField(
        null=True,
        blank=True
    )

    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='gateways',
    )

    class Meta:
        unique_together = [
            ['project', 'sn']
        ]

    @property
    def timezone(self):
        if not self.time_zone:
            return self.project.timezone
        return self.time_zone

    def __str__(self):
        if self.name is None:
            return self.sn
        return self.name


class Device(models.Model):

    dev_id = models.AutoField(primary_key=True)

    channel = models.CharField(max_length=128)

    id = models.CharField(max_length=10)

    name = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    desc = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    ready = models.BooleanField(default=False)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    gateway = models.ForeignKey(
        Gateway,
        on_delete=models.PROTECT,
        related_name='devices',
    )

    def __str__(self):
        if self.name is None:
            return '%s [%s-%s]' % (self.gateway, self.channel, self.id)
        return '%s %s' % (self.gateway, self.name)

    class Meta:
        unique_together = [
            ['gateway', 'channel', 'id']
        ]


class RTData(models.Model):

    logdt = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    date_time = models.DateTimeField(auto_now_add=True)

    discard = models.BooleanField(default=False)

    gateway = models.ForeignKey(
        Gateway,
        on_delete=models.PROTECT,
        related_name='data',
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    class Meta:
        unique_together = [
            ['gateway', 'date_time'],
        ]


class DataNone(models.Model):

    dblink = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    name = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    value = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    unit = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    discard = models.BooleanField(default=False)

    data = models.ForeignKey(
        RTData,
        related_name='nodes',
        on_delete=models.PROTECT
    )

    device = models.ForeignKey(
        Device,
        related_name='nodes',
        on_delete=models.PROTECT
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['device', 'data', 'name'])
        ]


class RTAlarm(models.Model):

    logdt = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    date_time = models.DateTimeField(auto_now_add=True)

    name = models.CharField(
        max_length=256,
        null=True,
        blank=True
    )

    value = models.CharField(
        max_length=2048,
        null=True,
        blank=True
    )

    threadhold_value = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    unit = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    type = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    flag = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    device = models.ForeignKey(
        Device,
        related_name='alarms',
        on_delete=models.PROTECT
    )

    class Meta:
        indexes = [
            models.Index(fields=['device', 'logdt'])
        ]

    re_int_charts = re.compile(r'^\D*(\d*).*$')

    @property
    def int_value(self):
        int_chars = self.re_int_charts.match(self.value)
        if int_chars:
            int_val = int_chars.groups()[0]
            if int_val:
                return int(int_val)


class TrendLogData(models.Model):

    date_time = models.DateTimeField()

    dblink = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )

    value = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    unit = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    device = models.ForeignKey(
        Device,
        related_name='trend_log_data',
        on_delete=models.PROTECT
    )

    class Meta:
        unique_together = [
            ['device', 'dblink', 'date_time'],
        ]

        indexes = [
            models.Index(fields=['device', 'name', 'date_time'])
        ]


class Measure(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='Measure name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Measure description'
    )

    var_name = models.CharField(
        max_length=128,
        help_text='Device variable name',
        null=True,
        blank=True,
    )

    calculator = models.CharField(
        max_length=20,
        help_text='Measuer calculator',
        choices=Calculators.choices(),
        default=Calculators.default_calculator
    )

    calculator_args = models.JSONField(
        default=list,
        null=True,
        blank=True
    )

    calculator_kwargs = models.JSONField(
        default=dict,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    extra_data = models.JSONField(default=dict, null=True, blank=True)

    local = models.ForeignKey(
        Local,
        on_delete=models.CASCADE,
        related_name='measures',
    )

    unit_cost = models.ForeignKey(
        UnitCost,
        on_delete=models.CASCADE,
        related_name='measures',
    )

    def make_invoice_item_desc(self, result_data):
        if self.unit_cost.invoice_item_format is None:
            return 'Cargo de energía'
        context = dict(result_data)
        context.update({
            'start_date': datetime.fromisoformat(result_data['start_date']),
            'end_date': datetime.fromisoformat(result_data['start_date']),
            'local': self.local,
            'unit_cost': self.unit_cost,
        })
        template = Template(self.unit_cost.invoice_item_format)
        return template.render(Context(context))

    def calculate(self, *args, **kwargs):
        calculator = Calculators.get(self.calculator)
        return calculator(self, *args, **kwargs)

    def __str__(self):
        return self.name


class Alert(models.Model):

    name = models.CharField(max_length=128)

    enabled = models.BooleanField(default=True)

    emails = ArrayField(
        models.EmailField(),
        null=True,
        blank=True
    )

    from_email = models.EmailField(null=True, blank=True)

    from_email_name = models.CharField(max_length=50, null=True, blank=True)

    device_channel = models.CharField(max_length=128)

    device_id = models.CharField(max_length=10)

    subject_template = models.TextField(null=True)

    msg_template = models.TextField(null=True)

    html_msg_template = HTMLField(null=True)

    gateway = models.ForeignKey(
        Gateway,
        on_delete=models.PROTECT,
        related_name='alerts',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    indexes = [
        models.Index(fields=['gateway', 'device_channel', 'device_id'])
    ]

    def send(self, rt_alarm):
        return send_alert(self, rt_alarm)

import re
from datetime import datetime
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import (
    Subquery, OuterRef, FloatField, Case, When, Value
)
from django.db.models.functions import Cast


class PlzRAirConditioningConsumption:

    id = 'PLZR_CONSUMO_AA'
    name = 'Consumo de AA'

    measure_overwrite_scheme = {
        'type': 'dict',
        'keys': {
            'result': {
                'type': 'number'
            }
        }
    }

    table_view_fields = [
        'tv_result'
    ]

    def tv_result(self, data):
        value = data['result']
        return '%.2f' % (value)

    tv_result.name = 'Resultado'

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.device').objects

    def get_min_max_trends(self, measure, var_data, start_date, end_date):
        name = var_data.get('name')
        device_id = var_data.get('device_id')
        if None in [name, device_id]:
            raise ValidationError('not null')

        device = None
        try:
            device = self.device_manager.get(
                gateway__project=measure.local.project,
                dev_id=device_id
            )
        except ObjectDoesNotExist:
            raise ValidationError('Device id not valid')

        try:
            start_trend_log = device.trend_log_data.filter(
                name=name,
                date_time__gte=start_date
            ).order_by('date_time').first()
        except ObjectDoesNotExist:
            raise ValidationError('Min not fund')

        try:
            end_trend_log = device.trend_log_data.filter(
                name=name,
                date_time__lte=end_date
            ).order_by('-date_time').first()
        except ObjectDoesNotExist:
            raise ValidationError('max not found')

        return (start_trend_log, end_trend_log)

    def __call__(self, measure, *args, **kwargs):
        start_date = kwargs['start_date']
        end_date = kwargs['end_date']
        general_vars = measure.calculator_kwargs.get('general_vars', [])
        level_vars = measure.calculator_kwargs.get('level_vars', [])
        local_vars = measure.calculator_kwargs.get('local_vars', [])
        percentage = measure.calculator_kwargs.get('percentage', 100)
        ret_data = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        }
        general_diff = 0.0
        for var_data in general_vars:
            s_trend, e_trend = self.get_min_max_trends(
                measure, var_data, start_date, end_date
            )
            name = var_data.get('name')
            start_value = float(s_trend.value)
            end_value = float(e_trend.value)
            ret_data['G_%s_start_date' % name] = s_trend.date_time.isoformat()
            ret_data['G_%s_start_value' % name] = start_value
            ret_data['G_%s_end_date' % name] = e_trend.date_time.isoformat()
            ret_data['G_%s_end_value' % name] = end_value
            diff = end_value - start_value
            ret_data['G_%s_diff' % name] = diff
            general_diff += diff
        ret_data['G_diff'] = general_diff

        level_diff = 0.0
        for var_data in level_vars:
            s_trend, e_trend = self.get_min_max_trends(
                measure, var_data, start_date, end_date
            )
            name = var_data.get('name')
            start_value = float(s_trend.value)
            end_value = float(e_trend.value)
            ret_data['LE_%s_start_date' % name] = s_trend.date_time.isoformat()
            ret_data['LE_%s_start_value' % name] = start_value
            ret_data['LE_%s_end_date' % name] = e_trend.date_time.isoformat()
            ret_data['LE_%s_end_value' % name] = end_value
            diff = end_value - start_value
            ret_data['LE_%s_diff' % name] = diff
            level_diff += diff
        ret_data['LE_diff'] = level_diff

        local_diff = 0.0
        for var_data in local_vars:
            s_trend, e_trend = self.get_min_max_trends(
                measure, var_data, start_date, end_date
            )
            name = var_data.get('name')
            start_value = float(s_trend.value)
            end_value = float(e_trend.value)
            ret_data['LO_%s_start_date' % name] = s_trend.date_time.isoformat()
            ret_data['LO_%s_start_value' % name] = start_value
            ret_data['LO_%s_end_date' % name] = e_trend.date_time.isoformat()
            ret_data['LO_%s_end_value' % name] = end_value
            diff = end_value - start_value
            ret_data['LO_%s_diff' % name] = diff
            local_diff += diff
        ret_data['LO_diff'] = local_diff

        ret_data['AIRE_FRESCO'] = (general_diff * local_diff) / level_diff
        pre_result = ret_data['AIRE_FRESCO'] + local_diff
        ret_data['pre_result'] = pre_result
        ret_data['result'] = (percentage * pre_result) / 100
        # ret_data['unit_cost'] = measure.unit_cost.value
        # ret_data['amount'] = ret_data['result'] * ret_data['unit_cost']

        return ret_data


class PlzRAirConditioningOccupation:

    id = 'PLZR_OCCUPATION_AA'
    name = 'Ocupación de AA'

    @property
    def tld_manager(self):
        return apps.get_model('x6gateapi.trendlogdata').objects

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.device').objects

    def __call__(self, measure, *args, **kwargs):
        device_id = measure.calculator_kwargs.get('device_id')
        var_names = measure.calculator_kwargs.get('names', [])
        error_range = measure.calculator_kwargs.get('error_range')
        len_vars = len(var_names)
        device = self.device_manager.get(
            gateway__project=measure.local.project,
            dev_id=device_id
        )
        time_zone = device.gateway.timezone
        qs = self.tld_manager.filter(
            device__gateway__project=measure.local.project,
            device=device,
            name__in=var_names
        ).order_by('date_time').distinct('date_time').values('date_time')
        for var_name in var_names:
            safe_name = re.sub(r"[^a-zA-Z0-9_\-.]+", "", var_name)
            annotate = {
                safe_name: Cast(
                    Subquery(
                        self.tld_manager.filter(
                            date_time=OuterRef('date_time'),
                            device=device,
                            name=var_name
                        ).values('value')
                    ),
                    output_field=FloatField()
                ) - Cast(
                    Subquery(
                        self.tld_manager.filter(
                            date_time__lt=OuterRef('date_time'),
                            device=device,
                            name=var_name
                        ).order_by('-date_time').values('value')[:1]
                    ),
                    output_field=FloatField()
                )
            }
            qs = qs.annotate(
                **annotate
            )
            wen = {
                '%s__gt' % (safe_name): error_range,
                'then': Value(1)
            }
            annotate = {
                '%s_val' % (safe_name): Case(
                    When(**wen),
                    default=Value(0)
                )
            }
            qs = qs.annotate(
                **annotate
            )
            annotate = {
                'from_date': Subquery(
                    self.tld_manager.filter(
                        date_time__lt=OuterRef('date_time'),
                        device=device,
                        name=var_name
                    ).order_by('-date_time').values('date_time')[:1]
                )
            }
            qs = qs.annotate(
                **annotate
            )
        ret = []
        for row in qs.iterator():
            suma = 0
            for key_name in row:
                if key_name.endswith('_val'):
                    suma += row[key_name]
            date = row['date_time'].astimezone(time_zone)
            if row['from_date'] is None:
                continue
            from_date = row['from_date'].astimezone(time_zone)

            ret.append({
                'from_date': from_date.strftime('%Y-%m-%d %H:%M'),
                'to_date': date.strftime('%Y-%m-%d %H:%M'),
                'occupation': (suma * 100) / len_vars,
            })
        return ret


class PlzRAirConditioningDailyConsumption:

    id = 'PLZR_CONSUMOTD_AA'
    name = 'Consumo de Total diario AA'

    @property
    def tld_manager(self):
        return apps.get_model('x6gateapi.trendlogdata').objects

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.device').objects

    def __call__(self, measure, *args, **kwargs):
        device_id = measure.calculator_kwargs.get('device_id')
        var_names = measure.calculator_kwargs.get('names', [])
        len_vars = len(var_names)
        device = self.device_manager.get(
            gateway__project=measure.local.project,
            dev_id=device_id
        )
        time_zone = device.gateway.timezone
        qs = self.tld_manager.filter(
            device__gateway__project=measure.local.project,
            device=device,
            name__in=var_names
        ).order_by('date_time').distinct('date_time').values('date_time')
        safe_names = []
        for var_name in var_names:
            safe_name = re.sub(r"[^a-zA-Z0-9_\-.]+", "", var_name)
            safe_names.append(safe_name)
            annotate = {
                safe_name: Cast(
                    Subquery(
                        self.tld_manager.filter(
                            date_time=OuterRef('date_time'),
                            device=device,
                            name=var_name
                        ).values('value')
                    ),
                    output_field=FloatField()
                ) - Cast(
                    Subquery(
                        self.tld_manager.filter(
                            date_time__lt=OuterRef('date_time'),
                            device=device,
                            name=var_name
                        ).order_by('-date_time').values('value')[:1]
                    ),
                    output_field=FloatField()
                ),
                'from_date': Subquery(
                    self.tld_manager.filter(
                        date_time__lt=OuterRef('date_time'),
                        device=device,
                        name=var_name
                    ).order_by('-date_time').values('date_time')[:1]
                )
            }
            qs = qs.annotate(
                **annotate
            )
        ret = []
        for row in qs.iterator():
            suma = 0
            for safe_name in safe_names:
                suma += row[safe_name] if row[safe_name] is not None else 0
            date = row['date_time'].astimezone(time_zone)
            if row['from_date'] is None:
                continue
            from_date = row['from_date'].astimezone(time_zone)

            ret.append({
                'from_date': from_date.strftime('%Y-%m-%d %H:%M'),
                'to_date': date.strftime('%Y-%m-%d %H:%M'),
                'daily_consumption': (suma * 100) / len_vars,
            })
        return ret


class BussParkWConsumption:

    id = 'BUSSPARK_CONSUMO_W'
    name = 'Consumo de Kwh'

    table_view_fields = [
        'tv_start_date',
        'tv_start_value',
        'tv_end_date',
        'tv_end_value',
        'tv_result'
    ]

    measure_overwrite_scheme = {
        'type': 'dict',
        'keys': {
            'start_date': {
                'type': 'string'
            },
            'start_value': {
                'type': 'number'
            },
            'end_date': {
                'type': 'string'
            },
            'end_value': {
                'type': 'number'
            },
            'result': {
                'type': 'number'
            },
            'history': {
                'type': 'array',
                'maxItems': 10,
                'items': {
                    'type': 'dict',
                    'keys': {
                        'date': {
                            'type': 'string',
                        },
                        'value': {
                            'type': 'number',
                        }
                    }
                }
            },
            'balance_due': {
                'type': 'dict',
                'keys': {
                    '0_30': {
                        'type': 'number',
                        'title': '0-30 días',
                        'default': 0
                    },
                    '30_60': {
                        'type': 'number',
                        'title': '30-60 días',
                        'default': 0
                    },
                    '60_90': {
                        'type': 'number',
                        'title': '60-90 días',
                        'default': 0
                    },
                    '90': {
                        'type': 'number',
                        'title': '90+ días',
                        'default': 0
                    },
                }
            }
        }
    }

    def tv_start_date(self, data):
        value = datetime.fromisoformat(data['start_date'])
        return value.strftime('%Y-%m-%d %H:%M')

    tv_start_date.name = 'Start date'

    def tv_start_value(self, data):
        return '%.2f' % (data['start_value'])

    tv_start_value.name = 'Start value'

    def tv_end_date(self, data):
        value = datetime.fromisoformat(data['end_date'])
        return value.strftime('%Y-%m-%d %H:%M')

    tv_end_date.name = 'End date'

    def tv_end_value(self, data):
        return '%.2f' % (data['end_value'])

    tv_end_value.name = 'End value'

    def tv_result(self, data):
        return '%.2f' % (data['result'])

    tv_result.name = 'Result'

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.device').objects

    def _get_rtdata_demand(self, device, var_name, start_date, end_date):
        values = []
        nodes = device.nodes.filter(
            removed_at__isnull=True,
            discard=False,
            name=var_name,
            data__discard=False,
            data__removed_at__isnull=True,
            data__date_time__gte=start_date,
            data__date_time__lte=end_date,
        )
        for node in nodes:
            try:
                values.append(float(node.value))
            except (TypeError, ValueError):
                pass
        if not values:
            return None
        return max(values)

    def _get_rtdata_values(self, device, var_name, start_date, end_date):
        start_none = device.nodes.filter(
            removed_at__isnull=True,
            discard=False,
            name=var_name,
            data__discard=False,
            data__removed_at__isnull=True,
            data__date_time__gte=start_date
        ).select_related('data').order_by('data__date_time').first()
        end_node = device.nodes.filter(
            removed_at__isnull=True,
            discard=False,
            name=var_name,
            data__discard=False,
            data__removed_at__isnull=True,
            data__date_time__lte=end_date
        ).select_related('data').order_by('-data__date_time').first()
        if start_none and end_node:
            return [
                (start_none.data.date_time, float(start_none.value)),
                (end_node.data.date_time, float(end_node.value)),
            ]
        return None

    def _get_history_values(self, device, var_name, start_date, header, mea):
        max = 12
        count_i = 0
        ret = []
        current_month = start_date.month
        current_year = start_date.year
        his_data = mea.extra_data.get('history', {})
        while count_i < max:
            count_i += 1
            s_start_date = datetime(
                day=1, month=current_month, year=current_year,
                tzinfo=header.client.timezone
            )
            s_start_date_key = s_start_date.strftime('%m-%Y')
            if s_start_date_key in his_data:
                ret.append({
                    'date': s_start_date_key,
                    'value': his_data[s_start_date_key]
                })
            else:
                s_end_date = datetime(
                    day=1,
                    month=(current_month + 1 if current_month < 12 else 1),
                    year=(
                        current_year
                        if current_month < 12 else
                        current_year + 1
                    ),
                    tzinfo=header.client.timezone
                )
                result = self._get_rtdata_values(
                    device,
                    var_name,
                    s_start_date,
                    s_end_date
                )
                if result is None:
                    break
                ret.append({
                    'date': s_start_date_key,
                    'value': result[1][1] - result[0][1]
                })
            current_month = (current_month - 1 if current_month > 1 else 12)
            current_year = (
                current_year if current_month > 1 else current_year - 1
            )
        ret.reverse()
        return ret

    def __call__(self, measure, *args, **kwargs):
        start_date = kwargs['start_date']
        end_date = kwargs['end_date']
        header = kwargs.get('header')
        device_id = measure.calculator_kwargs.get('device_id')
        var_name = measure.calculator_kwargs.get('var_name')
        var_type = measure.calculator_kwargs.get('var_type', 'rtdata')
        device = self.device_manager.get(
            gateway__project=measure.local.project,
            dev_id=device_id
        )
        time_zone = device.gateway.timezone

        data_values = None
        if var_type == 'rtdata':
            data_values = self._get_rtdata_values(
                device, var_name, start_date, end_date
            )
        if data_values is None:
            raise Exception("Error")
        start_data_date, start_data_value = data_values[0]
        end_data_date, end_data_value = data_values[1]
        ret_data = {}

        ret_data['start_date'] = start_data_date.astimezone(
            time_zone
        ).isoformat()
        ret_data['start_value'] = start_data_value

        ret_data['end_date'] = end_data_date.astimezone(
            time_zone
        ).isoformat()
        ret_data['end_value'] = end_data_value
        ret_data['result'] = end_data_value - start_data_value
        ret_data['history'] = self._get_history_values(
            device, var_name, start_date, header, measure
        )
        ret_data['meter'] = var_name
        ret_data['measure_id'] = measure.id
        ret_data['balance_due'] = {
            '0_30': 0,
            '30_60': 0,
            '60_90': 0,
            '90': 0,
        }
        ret_data['demand'] = self._get_rtdata_demand(
            device, var_name + '-DEMAND', start_date, end_date
        )
        return ret_data


CALCULATORS_HANDLERS = [
    PlzRAirConditioningConsumption(),
    PlzRAirConditioningOccupation(),
    PlzRAirConditioningDailyConsumption(),
    BussParkWConsumption(),
]


class Calculators:

    @classmethod
    def choices(cls):
        choices = []
        for calculator in CALCULATORS_HANDLERS:
            if hasattr(calculator, 'name') and hasattr(calculator, 'id'):
                choices.append(
                    (getattr(calculator, 'id'), getattr(calculator, 'name'))
                )
        return choices

    @classmethod
    def get(cls, calculator_id):
        for calculator in CALCULATORS_HANDLERS:
            if getattr(calculator, 'id') == calculator_id:
                return calculator
        raise NotImplementedError(
            'Calculator id "%s" not implemented' % calculator_id
        )

    default_calculator = 'TEST'

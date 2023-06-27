import re
from datetime import datetime
from django.apps import apps
from django.db.models import Subquery, OuterRef
from django.db.models.manager import Manager
from megedc.x6gateapi.models import RTData


class DataExportManager(Manager):

    @property
    def datanode_manager(self):
        return apps.get_model('x6gateapi.datanone').objects

    @property
    def device_manager(self):
        return apps.get_model('x6gateapi.device').objects

    def export_queryset(self, **kwargs):
        queryset = self

        from_date_time = kwargs.get('from_date_time', None)
        if from_date_time is not None:
            from_date_time = datetime.fromisoformat(from_date_time)
            queryset = queryset.filter(date_time__gte=from_date_time)

        to_date_time = kwargs.get('to_date_time', None)
        if to_date_time is not None:
            to_date_time = datetime.fromisoformat(to_date_time)
            queryset = queryset.filter(date_time__lte=to_date_time)

        discard = kwargs.get('discard', None)
        gateway_id, var_names = self.get_var_names(full=True, **kwargs)
        annotations = {}
        for device_id in var_names:
            for var_name, dev_var_name in var_names[device_id]:
                filters = {
                    'data': OuterRef('pk'),
                    'name': dev_var_name,
                    'device_id': device_id,
                    'removed_at__isnull': True
                }
                value_qs = self.datanode_manager.filter(**filters)
                annotations[var_name] = Subquery(value_qs.values('value')[:1])
        if not annotations:
            return self.none()
        queryset = queryset.annotate(**annotations).filter(
            gateway_id=gateway_id
        )
        if discard is not None:
            queryset = queryset.filter(
                discard=discard,
                removed_at__isnull=True
            )
        return queryset

    def get_var_names(self, **kwargs):
        device_ids = kwargs.get('device_ids', [])
        gateway_id = kwargs.get('gateway_id')
        v_allow = kwargs.get('vars', [])
        discard = kwargs.get('discard', None)
        dev_qs = self.device_manager
        if gateway_id:
            dev_qs = dev_qs.filter(
                gateway_id=gateway_id,
                removed_at__isnull=True
            )
        else:
            dev_qs = dev_qs.filter(
                pk__in=device_ids,
                removed_at__isnull=True
            )

        var_names = {}
        for result_row in dev_qs.values_list('dev_id', 'name', 'gateway__id'):
            if gateway_id is None:
                gateway_id = result_row[2]
            else:
                if gateway_id != result_row[2]:
                    raise Exception(
                        'cannot export values from different gateways'
                    )
            dev_id = result_row[0]
            device_name = result_row[1]
            queryset = self.datanode_manager.filter(
                device_id=dev_id,
                removed_at__isnull=True
            )
            if discard is not None:
                queryset = queryset.filter(discard=discard)
            queryset = queryset.distinct('name')
            var_names[dev_id] = []
            for row in queryset.values_list('name'):
                dev_var_name = row[0]
                union_var_name = '%s__%s' % (
                    re.sub(r"[^a-zA-Z0-9_\-.]+", "", device_name),
                    re.sub(r"[^a-zA-Z0-9_\-.]+", "", dev_var_name)
                )
                if not v_allow or (v_allow and union_var_name in v_allow):
                    var_names[dev_id].append((union_var_name, dev_var_name))
        return (gateway_id, var_names)


class DataExport(RTData):

    objects = DataExportManager()

    class Meta:
        verbose_name = 'Data export'
        verbose_name_plural = 'Data export'
        proxy = True

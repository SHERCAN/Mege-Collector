from datetime import datetime
from django.http.response import Http404
from django.apps import apps
from megedc.utils import bool_from_str
from megedc.x6gateapi.serializers import (
    TrendLogDataSerializer, RTAlarmDataSerializer
)
from rest_framework.generics import (
    get_object_or_404,
    ListAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from megedc.billing.measue_calculators import Calculators
from megedc.data_export.serializers import FormDataUpdateViewSerializer


class RTDataExportAPIView(APIView):

    @property
    def dataexport_manager(self):
        return apps.get_model('data_export.dataexport').objects

    def get(self, request, *args, **kwargs):
        return Response(self.make_data(request))

    def make_data(self, request):
        device_ids = []
        discard = self.request.query_params.get('discard', 'f')
        if discard is not None:
            if discard == 'all':
                discard = None
            else:
                discard = bool_from_str(discard)
        for x in request.query_params.get('devices', '').split(','):
            if x:
                device_ids.append(int(x))
        gateway_id = request.query_params.get('gateway', None)
        if gateway_id:
            gateway_id = int(gateway_id)

        gateway_id, var_names_data = self.dataexport_manager.get_var_names(
            device_ids=device_ids,
            gateway_id=gateway_id
        )
        data_qs = self.dataexport_manager.export_queryset(
            device_ids=device_ids,
            gateway_id=gateway_id,
            discard=discard,
            from_date_time=request.query_params.get('from_date_time', None),
            to_date_time=request.query_params.get('to_date_time', None)
        )
        gateway = get_object_or_404(
            apps.get_model('x6gateapi.gateway').objects,
            pk=gateway_id
        )
        gateway_tz = gateway.timezone
        var_names = []
        for device_id in var_names_data:
            for var_name, _ in var_names_data[device_id]:
                var_names.append(var_name)
        for qs_row in data_qs.iterator():
            gateway_date_time = qs_row.date_time.astimezone(gateway_tz)
            row = {
                'logdt': qs_row.logdt,
                'utc_date_time': qs_row.date_time.isoformat(
                    ' ', timespec='seconds'
                ),
                'utc_year': gateway_date_time.strftime('%Y'),
                'utc_month': gateway_date_time.strftime('%m'),
                'utc_day': gateway_date_time.strftime('%d'),
                'utc_hour': gateway_date_time.strftime('%H'),
                'utc_minute': gateway_date_time.strftime('%M'),
                'gateway_date_time': gateway_date_time.isoformat(
                    ' ', timespec='seconds'
                ),
                'gateway_year': gateway_date_time.strftime('%Y'),
                'gateway_month': gateway_date_time.strftime('%m'),
                'gateway_day': gateway_date_time.strftime('%d'),
                'gateway_hour': gateway_date_time.strftime('%H'),
                'gateway_minute': gateway_date_time.strftime('%M'),
            }
            for var_name in var_names:
                row[var_name] = getattr(qs_row, var_name, None)
            yield row


class DataListAPIView(ListAPIView):

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        gw_id = self.request.query_params.get('gateway')

        from_date_time = self.request.query_params.get('from_date_time', None)
        if from_date_time is not None:
            from_date_time = datetime.fromisoformat(from_date_time)
            queryset = queryset.filter(date_time__gte=from_date_time)

        to_date_time = self.request.query_params.get('to_date_time', None)
        if to_date_time is not None:
            to_date_time = datetime.fromisoformat(to_date_time)
            queryset = queryset.filter(date_time__lte=to_date_time)

        if not gw_id:
            raise Http404()
        return queryset.filter(device__gateway__id=gw_id)

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            removed_at__isnull=True
        )
        return queryset.select_related('device', 'device__gateway')


class TrendLogDataListAPIView(DataListAPIView):

    serializer_class = TrendLogDataSerializer

    @property
    def queryset(self):
        return apps.get_model('x6gateapi.trendlogdata').objects


class RTAlarmDataListAPIView(DataListAPIView):

    serializer_class = RTAlarmDataSerializer

    @property
    def queryset(self):
        return apps.get_model('x6gateapi.RTAlarm').objects


class FormDataViewAPIView(APIView):

    def __init__(self, *args, **kwargs):
        self._client = None
        self._project = None
        self._gateway = None
        super().__init__(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        return Response({
            'projects': self.projects,
            'gateways': self.gateways,
            'devices': self.devices,
            'vars': self.vars
        })

    @property
    def client(self):
        if self._client is None:
            client_id = self.request.query_params.get('client_id')
            chgc_client = self.request.session.get('chgc_client')
            if chgc_client:
                client_id = chgc_client
            if client_id is None:
                return None
            self._client = get_object_or_404(
                apps.get_model('general.client').objects.all(),
                pk=client_id
            )
        return self._client

    @property
    def project(self):
        if self._project is None:
            project_id = self.request.query_params.get('project_id')
            if project_id is None:
                return None
            self._project = get_object_or_404(
                self.client.projects.all().filter(
                    removed_at__isnull=True
                ),
                pk=project_id
            )
        return self._project

    @property
    def gateway(self):
        if self._gateway is None:
            gateway_id = self.request.query_params.get('gateway_id')
            if gateway_id is None:
                return None
            self._gateway = get_object_or_404(
                self.project.gateways.all().filter(
                    removed_at__isnull=True
                ),
                pk=gateway_id
            )
        return self._gateway

    @property
    def dataexport_manager(self):
        return apps.get_model('data_export.dataexport').objects

    @property
    def vars(self):
        device_ids = []
        ret = []
        for x in self.request.query_params.get('device_ids', '').split(','):
            if x:
                device_ids.append(int(x))
        if device_ids:
            _, var_names = self.dataexport_manager.get_var_names(
                device_ids=device_ids
            )
            for device_id in var_names:
                for var_name, _ in var_names[device_id]:
                    ret.append((var_name, var_name))
        return ret

    @property
    def projects(self):
        return self.client.projects.all().filter(
            removed_at__isnull=True
        ).values_list('pk', 'name')

    @property
    def gateways(self):
        if self.project is None:
            return None
        return self.project.gateways.all().filter(
            removed_at__isnull=True
        ).values_list('pk', 'sn', 'name')

    @property
    def devices(self):
        if self.gateway is None:
            return None
        return self.gateway.devices.all().filter(
            removed_at__isnull=True
        ).values_list(
            'pk',
            'name',
            'channel',
            'id',
        )


class MeasureCalcAPIView(RetrieveAPIView):

    queryset = apps.get_model('x6gateapi.Measure').objects

    def filter_queryset(self, queryset):
        if not self.request.user.is_superuser:
            queryset = queryset.filter(
                local__project__client=self.request.user.megeuser.client
            )
        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        calculator = Calculators.get(instance.calculator)
        data = calculator(instance)
        return Response(data)


class FormDataUpdateViewAPIView(CreateModelMixin,
                                DestroyModelMixin,
                                UpdateAPIView):

    serializer_class = FormDataUpdateViewSerializer
    queryset = apps.get_model('x6gateapi.DataNone').objects
    lookup_field = 'data__id'
    lookup_url_kwarg = 'data_id'
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            name=self.kwargs['var_name'],
            device__dev_id=self.kwargs['dev_id'],
            removed_at__isnull=True
        )

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Http404:
            return self.create(request, *args, **kwargs)

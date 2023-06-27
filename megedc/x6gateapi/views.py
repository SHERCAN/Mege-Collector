from datetime import datetime
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db.transaction import atomic
# from django.http import Http404
from rest_framework import status
from rest_framework.generics import (
    GenericAPIView,
    RetrieveAPIView,
    get_object_or_404
)
from megedc.x6gateapi import serializers
from rest_framework.response import Response
from rest_framework.settings import api_settings


class X6GateApiMixer():

    permission_classes = []


class GatewayMixier(X6GateApiMixer):

    def __init__(self, *args, **kwargs):
        self._project = None
        super().__init__(*args, **kwargs)

    @property
    def project_uuid(self):
        return self.kwargs.get('project_uuid')

    @property
    def project(self):
        if self._project is None:
            self._project = get_object_or_404(
                apps.get_model('general.project').objects,
                uuid=self.project_uuid,
                enabled=True
            )
        return self._project

    @property
    def queryset(self):
        return self.project.gateways.filter(enabled=True)


class GatewayCreateApiView(GatewayMixier, GenericAPIView):

    serializer_class = serializers.GatewaySerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def get_success_headers(self, data):
        try:
            return {'Location': str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}

    @atomic
    def create(self, request, *args, **kwargs):
        sn = request.data.get('sn')
        instance = None
        if sn is not None:
            try:
                instance = self.get_queryset().get(
                    project=self.project,
                    sn=sn
                )
            except ObjectDoesNotExist:
                pass
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['project'] = self.project
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(None, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()


class GatewayRetrieveAPIView(GatewayMixier, RetrieveAPIView):

    serializer_class = serializers.GatewaySerializer
    lookup_field = 'sn'
    lookup_url_kwarg = 'sn'


class DeviceMixser(GatewayMixier):

    def __init__(self, *args, **kwargs):
        self._gateway = None
        super().__init__(*args, **kwargs)

    @property
    def gateway_sn(self):
        return self.kwargs.get('sn')

    @property
    def gateway(self):
        if self._gateway is None:
            self._gateway = get_object_or_404(
                super().queryset,
                sn=self.gateway_sn,
            )
        return self._gateway

    @property
    def queryset(self):
        return self.gateway.devices.all()


class DeviceListCreateApiView(DeviceMixser, GenericAPIView):

    serializer_class = serializers.DeviceSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_success_headers(self, data):
        try:
            return {'Location': str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}

    @atomic
    def create(self, request, *args, **kwargs):
        gateway = self.gateway
        for device in request.data.get('device', []):
            instance = None
            try:
                instance = self.get_queryset().get(
                    gateway=gateway,
                    channel=device.get('channel'),
                    id=device.get('id')
                )
            except ObjectDoesNotExist:
                pass
            serializer = self.get_serializer(instance, data=device)
            serializer.is_valid(raise_exception=True)
            serializer.validated_data['gateway'] = gateway
            self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(None, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'device': serializer.data})


class RTDataCreateApiView(DeviceMixser, GenericAPIView):

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @atomic
    def create(self, request, *args, **kwargs):
        gateway = self.gateway
        logdt = request.data.get('logdt')
        rt_data = gateway.data.create(
            logdt=logdt,
            gateway=gateway
        )
        for device_data in request.data.get('device', []):
            device, _ = self.get_queryset().get_or_create(
                gateway=gateway,
                id=device_data.get('id'),
                channel=device_data.get('channel'),
                defaults={
                    'name': 'no name'
                }
            )
            for node in device_data.get('node', []):
                device.nodes.all().create(
                    dblink=node.get('dblink'),
                    name=node.get('name'),
                    value=node.get('value'),
                    unit=node.get('unit'),
                    device=device,
                    data=rt_data,
                    discard=(not device.ready)
                )
        return Response(None, status=status.HTTP_200_OK)


# Todo: De esto nno hay pruebas echas
class RTAlarmCreateApiView(DeviceMixser, GenericAPIView):

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @atomic
    def create(self, request, *args, **kwargs):
        gateway = self.gateway
        for node_data in request.data.get('node', []):
            device, _ = self.get_queryset().get_or_create(
                gateway=gateway,
                id=node_data.get('id'),
                channel=node_data.get('channel'),
                defaults={
                    'name': 'no name'
                }
            )
            device.alarms.all().create(
                logdt=node_data.get('logdt'),
                name=node_data.get('name'),
                value=node_data.get('value'),
                threadhold_value=node_data.get('threadhold_value'),
                unit=node_data.get('unit'),
                type=node_data.get('type'),
                flag=node_data.get('flag'),
                device=device
            )
        return Response(None, status=status.HTTP_200_OK)


class TrendLogDataCreateApiView(DeviceMixser, GenericAPIView):

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @atomic
    def create(self, request, *args, **kwargs):
        for device_data in request.data.get('device', []):
            gateway = self.gateway
            device, _ = self.get_queryset().get_or_create(
                gateway=gateway,
                id=device_data.get('id'),
                channel=device_data.get('channel'),
                defaults={
                    'name': device_data.get('name', 'no_name')
                }
            )
            for trendlog in device_data.get('trendlog', []):
                for node in trendlog.get('data', []):
                    device.trend_log_data.all().get_or_create(
                        device=device,
                        date_time=device.gateway.timezone.localize(
                            datetime.fromisoformat(node.get('date_time'))
                        ),
                        dblink=trendlog.get('dblink'),
                        defaults={
                            'name': trendlog.get('name'),
                            'value': node.get('value'),
                            'unit': node.get('unit'),
                        }
                    )
        return Response(None, status=status.HTTP_200_OK)

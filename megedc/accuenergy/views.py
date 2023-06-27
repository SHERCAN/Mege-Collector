import pytz
from datetime import datetime
from django.apps import apps
from django.http import Http404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404


class AccuenergyPostChannel(APIView):

    def __init__(self, *args, **kwargs):
        self._project = None
        self._gateway = None
        self._device = None
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
    def gateway(self):
        if self._gateway is None:
            data = self.request.data
            sn = data.get('device_name', None)
            if sn is None:
                raise Http404()
            self._gateway, created = self.project.gateways.get_or_create(
                sn=sn, project=self.project,
                defaults={
                    'gateway_type': data.get('device_model', None),
                    'name': sn,
                    'site': {},
                    'owner': {},
                    'room': {},

                }
            )
        return self._gateway

    @property
    def device(self):
        if self._device is None:
            self._device, created = self.gateway.devices.get_or_create(
                id='0', channel='0', gateway=self.gateway,
                defaults={
                    'ready': True,
                    'name': 'dev'
                }
            )
        return self._device

    def post(self, request, *args, **kwargs):
        self.process_data()
        return Response(None, status=status.HTTP_201_CREATED)

    def process_data(self):
        data = self.request.data
        timestamps = data.get('timestamp', [])
        readings = data.get('readings', [])
        index = 0
        for timestamp in timestamps:
            tr_date = pytz.timezone(
                str(self.gateway.timezone)
            ).localize(datetime.fromtimestamp(int(timestamp)))
            rt_data, created = self.gateway.data.get_or_create(
                gateway=self.gateway,
                date_time=tr_date,
                defaults={
                    'logdt': tr_date.strftime('%Y-%m-%d %H:%M'),
                }
            )
            if created:
                rt_data.date_time = tr_date
                rt_data.save()
                for read_data in readings:
                    name = read_data.get('param')
                    value = read_data.get('value')[index]
                    rt_data.nodes.create(
                        device=self.device,
                        data=rt_data,
                        name=name,
                        value=value
                    )
            index += 1

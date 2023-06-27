import csv
import pytz
from argparse import FileType
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.transaction import atomic
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):

    def __init__(self, *args, **kwargs):
        self._devices = {}
        self._gateway = None
        self._rtdata = {}
        super().__init__(*args, **kwargs)

    help = 'Import data data from csv'

    def add_arguments(self, parser):
        parser.add_argument(
            '-u', '--uuid', required=True, type=str,
            help=('Project uuid')
        )
        parser.add_argument(
            'csv_file', type=FileType('r'),
            help=('Path of the csv file to import.')
        )

    def _load_data(self, csv_file):
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            yield row

    def get_gateway(self, row):
        if self._gateway is None:
            self._gateway, _ = self.project.gateways.all().get_or_create(
                sn=row['sn'],
                defaults={
                    'name': row['sn'],
                    'site': {},
                    'owner': {},
                    'room': {},
                    'project': self.project
                }
            )
        return self._gateway

    def _get_device(self, row):
        iid = '%s_%s' % (row['channel'], row['id'])
        if iid not in self._devices:
            gw = self.get_gateway(row)
            device, _ = gw.devices.all().get_or_create(
                channel=row['channel'],
                id=row['id'],
                defaults={
                    'ready': True,
                    'name': ('dev_%s_%s' % (row['channel'], row['id'])),
                    'desc': ('dev %s %s' % (row['channel'], row['id'])),
                    'gateway': gw
                }
            )
            self._devices[iid] = device
        return self._devices[iid]

    def _get_rtdata(self, row):
        iid = row['date_time']
        if iid not in self._rtdata:
            gw = self.get_gateway(row)
            date_time = pytz.timezone(
                settings.TIME_ZONE
            ).localize(parse_datetime(row['date_time']))
            rtdata, _ = gw.data.all().get_or_create(
                logdt=row['logdt'],
                date_time=date_time,
                defaults={
                    'gateway': gw,
                }
            )
            rtdata.date_time = date_time
            rtdata.save()
            self._rtdata[iid] = rtdata
        return self._rtdata[iid]

    @atomic
    def handle(self, *args, **options):
        p_uuid = options['uuid']
        self.project = apps.get_model('general.project').objects.get(pk=p_uuid)
        csv_file = options['csv_file']
        for row in self._load_data(csv_file):
            device = self._get_device(row)
            rtdata = self._get_rtdata(row)
            if device.nodes.filter(data=rtdata, name=row['name']).exists():
                continue
            device.nodes.create(
                dblink=row['dblink'],
                name=row['name'],
                value=row['value'],
                unit=row['unit'],
                data=rtdata,
                device=device
            )

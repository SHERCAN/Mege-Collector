from django.apps import apps
from rest_framework import serializers


class GatewaySerializer(serializers.ModelSerializer):

    class Meta:
        model = apps.get_model('x6gateapi.gateway')
        fields = [
            'sn',
            'name',
            'ver',
            'site',
            'owner',
            'room',
        ]


class DeviceSerializer(serializers.ModelSerializer):

    class Meta:
        model = apps.get_model('x6gateapi.device')
        fields = [
            'channel',
            'id',
            'name',
            'desc',
        ]


class DataSerializer(serializers.ModelSerializer):

    device_name = serializers.SerializerMethodField()
    device_id = serializers.SerializerMethodField()
    device_channel = serializers.SerializerMethodField()
    gateway_sn = serializers.SerializerMethodField()
    gateway_name = serializers.SerializerMethodField()

    def get_device_name(self, obj):
        return obj.device.name

    def get_device_id(self, obj):
        return obj.device.id

    def get_device_channel(self, obj):
        return obj.device.channel

    def get_gateway_sn(self, obj):
        return obj.device.gateway.sn

    def get_gateway_name(self, obj):
        return obj.device.gateway.name


class TrendLogDataSerializer(DataSerializer):

    class Meta:
        model = apps.get_model('x6gateapi.trendlogdata')
        fields = [
            'date_time',
            'dblink',
            'name',
            'value',
            'unit',
            'device_name',
            'device_id',
            'device_channel',
            'gateway_sn',
            'gateway_name',
        ]


class RTAlarmDataSerializer(DataSerializer):

    class Meta:
        model = apps.get_model('x6gateapi.RTAlarm')
        fields = [
            'logdt',
            'name',
            'value',
            'threadhold_value',
            'unit',
            'type',
            'flag',
            'device_name',
            'device_id',
            'device_channel',
            'gateway_sn',
            'gateway_name',
        ]

from django.apps import apps
from rest_framework import serializers
from django.utils.timezone import localtime


class FormDataUpdateViewSerializer(serializers.ModelSerializer):

    class Meta:
        model = queryset = apps.get_model('x6gateapi.DataNone')
        fields = [
            'value',
        ]
        extra_kwargs = {'value': {'write_only': True}}

    def create(self, validated_data):
        view = self.context['view']
        validated_data.update({
            'name': view.kwargs['var_name'],
            'device_id': view.kwargs['dev_id'],
            'data_id': view.kwargs['data_id'],
        })
        return super().create(validated_data)

    def update(self, instance, validated_data):
        value = validated_data['value']
        if value == '':
            validated_data['removed_at'] = localtime()
            validated_data.pop('value')
        return super().update(instance, validated_data)

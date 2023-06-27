from datetime import datetime
from django import forms
from django.apps import apps
from django.contrib.admin import helpers
from django.contrib.admin.widgets import AdminDateWidget
from django.core.exceptions import ValidationError
from django.db.transaction import atomic
from django.http.response import HttpResponseBadRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from megedc.accuenergy.api_client import AccuenergyApiClient
from megedc.emporiaenergy.partner_api import (
    partner_api,
    PartnerApiException,
    PartnerApiResponseException,
)
from megedc.x6gateapi import EE_RESOLUTION_CHOICES
from megedc.x6gateapi.tasks import emporia_energy_gateway_sync


class MainForm(forms.Form):

    project = forms.ChoiceField(
        required=True,
    )

    gateway_type = forms.ChoiceField(
        choices=[
            ('emporia_energy', 'Emporia Energy'),
            ('acurev_2110', 'AcuRev 2100'),
        ],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        queryset = apps.get_model('general.project').objects.filter(
            removed_at__isnull=True
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(
                client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    client_id=chgc_client
                )
        queryset = queryset.values_list('uuid', 'name').order_by('name')
        self.fields['project'].choices = list(queryset)


class EECredentialsForm(forms.Form):

    host = forms.CharField(
        required=True,
    )

    port = forms.IntegerField(
        min_value=1,
        max_value=65535,
        required=True,
    )

    email = forms.EmailField(
        required=True,
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
    )

    def clean(self):
        cleaned_data = super().clean()
        host = cleaned_data.get('host')
        port = cleaned_data.get('port')
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if host and host and email and password:
            try:
                login = partner_api(
                    (email, password), host=host, port=port
                ).authenticate()
                if not login:
                    raise ValidationError(
                        'Could not access with these credentials.'
                    )
            except PartnerApiResponseException as exce:
                if exce.response.is_auth_invalid_credentials:
                    raise ValidationError(
                        'Could not access with these credentials.'
                    ) from exce
            except PartnerApiException as exce:
                raise ValidationError(
                    'Could not connect to server.'
                ) from exce


_device_fields = [
    'manufacturer_device_id',
    'model',
    'firmware',
    'last_app_connect_time',
    'solar',
    'latitude',
    'longitude',
    'device_name',
    'device_connected',
]


class DeviceCheckboxSelectMultiple(forms.CheckboxSelectMultiple):

    option_template_name = 'megedc/x6gateapi/ee_checkbox_option.html'

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs=attrs)
        groups_ret = []
        for group_name, subgroup, index in groups:
            value = subgroup[0]['value']
            for device_data in self.devices_data:
                if value == device_data['manufacturer_device_id']:
                    subgroup[0]['device_data'] = device_data.copy()
                    break
            groups_ret.append((group_name, subgroup, index))
        return groups_ret

    def __init__(self, devices_data, *args, **kwargs):
        self.devices_data = devices_data
        super().__init__(*args, **kwargs)


class EEDevicesForm(forms.Form):

    def __init__(self, *args, **kwargs):
        devices_data = kwargs.pop('devices_data', None)
        super().__init__(*args, **kwargs)
        if devices_data:
            choices = []
            for device_data in devices_data:
                choices.append((
                    device_data['manufacturer_device_id'],
                    device_data['manufacturer_device_id']
                ))
            self.fields['device_ids'] = forms.MultipleChoiceField(
                choices=choices,
                widget=DeviceCheckboxSelectMultiple(devices_data),
                required=True,
            )


class EEChannelsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        devices_data = kwargs.pop('devices_data', [])
        devices_selected = kwargs.pop('devices_selected', {})
        super().__init__(*args, **kwargs)
        for device_id in devices_selected:
            choices = []
            channel_names = []
            label = 'Desconocido'
            for device_data in devices_data:
                if device_data['manufacturer_device_id'] == device_id:
                    channel_names = device_data['channel_names']
                    label = device_data['device_name']
            inx = 1
            for chan_name in channel_names:
                choices.append((inx, '(%s) %s' % (inx, chan_name)))
                inx += 1
            self.fields['device_%s' % (device_id)] = forms.MultipleChoiceField(
                choices=choices,
                widget=forms.CheckboxSelectMultiple,
                required=True,
                label=label
            )


class EEResolutionForm(forms.Form):

    RESOLUTION_CHOICES = EE_RESOLUTION_CHOICES

    def __init__(self, *args, **kwargs):
        devices_data = kwargs.pop('devices_data', [])
        devices_selected = kwargs.pop('devices_selected', {})
        super().__init__(*args, **kwargs)
        for device_id in devices_selected:
            label = 'Desconocido'
            for device_data in devices_data:
                if device_data['manufacturer_device_id'] == device_id:
                    label = device_data['device_name']
            self.fields['device_%s' % (device_id)] = forms.ChoiceField(
                choices=self.RESOLUTION_CHOICES,
                required=True,
                label=label
            )
            self.fields[
                'device_%s_from_date' % (device_id)
            ] = forms.DateTimeField(
                required=True,
                widget=AdminDateWidget,
                label='Get data from:'
            )


class AE_2100_CredentialsForm(forms.Form):

    remote_access_url = forms.URLField(
        required=True,
    )

    token = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'style': 'width:400px;'})
    )

    def clean(self):
        cleaned_data = super().clean()
        token = cleaned_data.get('token')
        remote_access_url = cleaned_data.get('remote_access_url')
        api_client = AccuenergyApiClient(remote_access_url, token)
        self.cleaned_data['dev_info'] = None
        try:
            dev_info = api_client.get_settings_deviceInfo()
            self.cleaned_data['dev_info'] = dev_info
        except Exception as exce:
            raise ValidationError(
                str(exce)
            )


class AE_2100_SummaryForm(forms.Form):

    collect_logs = forms.BooleanField(initial=True, required=False)


class GatewayMaker():

    title = 'Gateway creation'

    def __init__(self, admin, request):
        self.admin = admin
        self.request = request

    def _make_conext(self, context):
        end_context = self.admin.admin_site.each_context(self.request)
        end_context['title'] = self.title
        end_context.update(context)
        return end_context

    @property
    def session_data(self):
        return self.request.session.get('gateway_maker_data', {})

    @session_data.setter
    def session_data(self, value):
        self.request.session['gateway_maker_data'] = value

    def response(self):
        if self.request.method == 'GET':
            step = self.request.GET.get('step', 'main')
        elif self.request.method == 'POST':
            if self.request.POST.get('cancel', None):
                self.session_data = {}
                return self.make_redirect()
            step = self.request.POST.get('step', '')
        else:
            return HttpResponseBadRequest()
        step_handler_name = '%s_step' % step
        if hasattr(self, step_handler_name):
            return getattr(self, step_handler_name)()
        return HttpResponseBadRequest()

    def make_redirect(self, step=None):
        url = reverse('admin:gateway-maker')
        return HttpResponseRedirect(
            url if step is None else '%s?step=%s' % (
                reverse('admin:gateway-maker'),
                step
            )
        )

    # Desde aquí
    def main_step(self):
        session_data = self.session_data
        main_data = session_data.get('main', {})
        form = None
        form_kwargs = {
            'initial': main_data,
            'request': self.request,
        }
        formsets = [
            (
                None,
                {
                    'fields': (
                        'project',
                        'gateway_type',
                    )
                }
            )
        ]
        if self.request.method == 'POST':
            form = MainForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                main_data['gateway_type'] = form.cleaned_data['gateway_type']
                main_data['project'] = form.cleaned_data['project']
                session_data.update({'main': main_data})
                self.session_data = session_data
                return self.make_redirect('gateway_options')

        form = MainForm(**form_kwargs)
        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Select a grateway type',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
            'step': 'main'
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/gateway_make_main.html',
            self._make_conext(context)
        )

    def gateway_options_step(self):
        session_data = self.session_data
        main_data = session_data.get('main', {})
        gateway_type = main_data.get('gateway_type')
        if gateway_type is None:
            return self.make_redirect()
        step_handler_name = '%s_gateway_options_step' % (gateway_type)
        if hasattr(self, step_handler_name):
            return getattr(self, step_handler_name)()
        return self.make_redirect()

    def emporia_energy_gateway_options_step(self):
        session_data = self.session_data
        ee_data = session_data.get('emporia_energy', {
            'credentials': {
                'host': 'partner.emporiaenergy.com',
                'port': 50051
            }
        })
        credentials_data = ee_data.get('credentials')
        form_kwargs = {
            'initial': credentials_data
        }
        formsets = [
            (
                None,
                {
                    'fields': (
                        'host',
                        'port',
                        'email',
                        'password',
                    )
                }
            )
        ]
        if self.request.method == 'POST':
            form = EECredentialsForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                host = form.cleaned_data['host']
                port = form.cleaned_data['port']
                email = form.cleaned_data['email']
                password = form.cleaned_data['password']
                credentials_data.update({
                    'host': host,
                    'port': port,
                    'email': email,
                    'password': password,
                })
                ee_data.update({'credentials': credentials_data})
                session_data.update({'emporia_energy': ee_data})
                self.session_data = session_data
                return self.make_redirect(
                    'emporia_energy_devices'
                )
        else:
            form = EECredentialsForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Emporia host and credentials',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
            'step': 'emporia_energy_gateway_options'
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/ee_credentials.html',
            self._make_conext(context)
        )

    def emporia_energy_devices_step(self):
        session_data = self.session_data
        ee_data = session_data.get('emporia_energy')
        credentials_data = ee_data.get('credentials')
        devices_data = ee_data.get('devices_data', [])
        devices_selected = ee_data.get('devices_selected', [])
        email = credentials_data.get('email')
        password = credentials_data.get('password')
        host = credentials_data.get('host')
        port = credentials_data.get('port')

        if not (port or host or password or email):
            return self.make_redirect('emporia_energy_gateway_options')

        form_kwargs = {
            'devices_data': devices_data,
            'initial': {
                'device_ids': devices_selected
            }
        }

        if self.request.method == 'POST':
            form = EEDevicesForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                devices_selected = form.cleaned_data['device_ids']
                ee_data.update({'devices_selected': devices_selected})
                session_data.update({'emporia_energy': ee_data})
                self.session_data = session_data
                return self.make_redirect('emporia_energy_channels')
        elif self.request.method == 'GET':
            if not devices_data:
                ee_api = partner_api((email, password), host=host, port=port)
                try:
                    devices = ee_api.get_devices()
                except PartnerApiException as exce:
                    raise exce
                project_id = self.session_data.get('main', {}).get('project')
                for device in devices:
                    already_add = apps.get_model(
                        'x6gateapi.gateway'
                    ).objects.filter(
                        sn=device.manufacturer_device_id,
                        project_id=project_id
                    ).exists()
                    if already_add:
                        continue
                    device_data = {}
                    for filed_name in _device_fields:
                        device_data[filed_name] = getattr(device, filed_name)
                    device_data['channel_names'] = list(device.channel_names)
                    customer_info = None
                    if len(device.customer_info) > 0:
                        customer_info = device.customer_info[0]
                    device_data['customer_info'] = {
                        'first_name': customer_info.first_name,
                        'last_name': customer_info.last_name,
                        'email': customer_info.email
                    } if customer_info is not None else {
                        'first_name': None,
                        'last_name': None,
                        'email': None
                    }
                    devices_data.append(device_data)
                ee_data.update({'devices_data': devices_data})
                session_data.update({'emporia_energy': ee_data})
                self.session_data = session_data
            form = EEDevicesForm(**form_kwargs)

        formsets = []
        disable_next = True
        if devices_data:
            formsets = [
                (
                    None,
                    {
                        'fields': (
                            'device_ids',
                        )
                    }
                )
            ]
            disable_next = False
        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Emporia devices',
            'step': 'emporia_energy_devices',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
            'disable_next': disable_next,
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/ee_devices.html',
            self._make_conext(context)
        )

    def emporia_energy_channels_step(self):
        session_data = self.session_data
        ee_data = session_data.get('emporia_energy')
        devices_data = ee_data.get('devices_data', [])
        devices_selected = ee_data.get('devices_selected', [])
        devices_channels = ee_data.get('devices_channels', {})

        if not (devices_channels or devices_selected):
            return self.make_redirect('emporia_energy_devices')

        form_kwargs_initial = {}
        fields = []
        for device_id in devices_selected:
            channels = devices_channels.get(device_id, [])
            field_name = 'device_%s' % device_id
            fields.append(field_name)
            form_kwargs_initial[field_name] = channels
        form_kwargs = {
            'devices_data': devices_data,
            'devices_selected': devices_selected,
            'initial': form_kwargs_initial
        }
        formsets = [
            (
                None,
                {
                    'fields': fields
                }
            )
        ]

        if self.request.method == 'POST':
            form = EEChannelsForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                for device_id in devices_selected:
                    channels = form.cleaned_data['device_%s' % device_id]
                    devices_channels[device_id] = channels
                ee_data.update({'devices_channels': devices_channels})
                session_data.update({'emporia_energy': ee_data})
                self.session_data = session_data
                return self.make_redirect('emporia_energy_resolution')
        elif self.request.method == 'GET':
            form = EEChannelsForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Emporia devices channels',
            'step': 'emporia_energy_channels',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/ee_channels.html',
            self._make_conext(context)
        )

    def emporia_energy_resolution_step(self):
        session_data = self.session_data
        ee_data = session_data.get('emporia_energy')
        devices_data = ee_data.get('devices_data', [])
        devices_selected = ee_data.get('devices_selected', [])
        devices_resolution = ee_data.get('devices_resolution', {})
        devices_from_date = ee_data.get('devices_from_date', {})

        if not devices_selected:
            return self.make_redirect('emporia_energy_devices')

        form_kwargs_initial = {}
        fields = []
        for device_id in devices_selected:
            resolution = devices_resolution.get(device_id)
            field_name = 'device_%s' % device_id
            field_name_from_date = '%s_from_date' % field_name
            fields.extend([field_name, field_name_from_date])
            form_kwargs_initial[field_name] = resolution
            from_date = devices_from_date.get(device_id)
            if from_date:
                form_kwargs_initial[
                    field_name_from_date
                ] = datetime.fromisoformat(devices_from_date.get(device_id))
        form_kwargs = {
            'devices_data': devices_data,
            'devices_selected': devices_selected,
            'initial': form_kwargs_initial
        }
        formsets = [
            (
                None,
                {
                    'fields': fields
                }
            )
        ]

        if self.request.method == 'POST':
            form = EEResolutionForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                for device_id in devices_selected:
                    resolution = form.cleaned_data['device_%s' % device_id]
                    from_date = form.cleaned_data[
                        'device_%s_from_date' % device_id
                    ]
                    devices_resolution[device_id] = resolution
                    devices_from_date[device_id] = from_date.isoformat()
                ee_data.update({'devices_resolution': devices_resolution})
                ee_data.update({'devices_from_date': devices_from_date})
                session_data.update({'emporia_energy': ee_data})
                self.session_data = session_data
                return self.make_redirect('emporia_energy_confirm')
        elif self.request.method == 'GET':
            form = EEResolutionForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Emporia data resolution for device',
            'step': 'emporia_energy_resolution',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/ee_resolution.html',
            self._make_conext(context)
        )

    def emporia_energy_confirm_step(self):
        session_data = self.session_data
        ee_data = session_data.get('emporia_energy')
        devices_data = ee_data.get('devices_data', [])
        devices_selected = ee_data.get('devices_selected', [])
        devices_resolution = ee_data.get('devices_resolution', {})
        devices_channels = ee_data.get('devices_channels', {})
        devices_from_date = ee_data.get('devices_from_date', {})

        if not devices_selected:
            return self.make_redirect('emporia_energy_devices')

        form_kwargs = {}
        formsets = [
            (
                None,
                {
                    'fields': []
                }
            )
        ]

        confirm_data = []
        for device_id in devices_selected:
            data = None
            for device_data in devices_data:
                if device_data['manufacturer_device_id'] == device_id:
                    data = device_data
                    break
            resolution = devices_resolution.get(device_id)
            for value, label in EEResolutionForm.RESOLUTION_CHOICES:
                if value == resolution:
                    resolution_label = label
                    break
            channel_names = []
            channels = devices_channels.get(device_id, [])
            for channel in channels:
                channel_names.append(
                    '(%s) %s' % (
                        channel,
                        device_data['channel_names'][int(channel)-1]
                    )
                )
            confirm_data.append({
                'channels': channels,
                'channel_names': channel_names,
                'resolution': resolution,
                'resolution_label': resolution_label,
                'from_date': datetime.fromisoformat(
                    devices_from_date.get(device_id)
                ),
                'data': data
            })

        if self.request.method == 'POST':
            form = forms.Form(self.request.POST, **form_kwargs)
            if form.is_valid():
                self._emporia_energy_create_data(confirm_data)
                self.session_data = {}
                return HttpResponseRedirect(
                    reverse('admin:x6gateapi_gateway_changelist')
                )
        elif self.request.method == 'GET':
            form = forms.Form(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Emporia data resolution for device',
            'step': 'emporia_energy_confirm',
            'confirm_data': confirm_data,
            'submit_value': 'CREATE',
            'submit_name': 'CREATE',
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/ee_confirm.html',
            self._make_conext(context)
        )

    def _emporia_energy_create_data(self, data):
        project_id = self.session_data.get('main', {}).get('project')
        credentials = self.session_data.get(
            'emporia_energy', {}
        ).get('credentials')
        gateway_manager = apps.get_model('x6gateapi.Gateway').objects
        ides_for_jobs = []
        with atomic():
            for g_data in data:
                emp_dev_data = g_data['data']
                channels = g_data['channels']
                resolution = g_data['resolution']
                from_date = g_data['from_date']

                gateway = gateway_manager.create(
                    gateway_type='emporia_energy',
                    sn=emp_dev_data['manufacturer_device_id'],
                    name=emp_dev_data['device_name'],
                    ver=emp_dev_data['firmware'],
                    site={
                        'latitude': emp_dev_data['latitude'],
                        'longitude': emp_dev_data['longitude']
                    },
                    owner=emp_dev_data['customer_info'],
                    project_id=project_id,
                    room={},
                    extra_data={
                        'emporia_energy': {
                            'resolution': resolution,
                            'from_date': from_date.isoformat()
                        }
                    },
                    secret_extra_data={
                        'emporia_energy': credentials
                    }
                )
                for channel in channels:
                    gateway.devices.create(
                        channel=channel,
                        id='0',
                        name=emp_dev_data['channel_names'][int(channel)-1],
                        desc='',
                        ready=True,
                        gateway=gateway
                    )
                ides_for_jobs.append(gateway.id)
        emporia_energy_gateway_sync.delay(ides_for_jobs)

    def acurev_2110_gateway_options_step(self):
        session_data = self.session_data
        ac_data = session_data.get('acurev_2110', {
            'credentials': {
                'remote_access_url': None,
                'token': None
            }
        })
        credentials_data = ac_data.get('credentials')
        form_kwargs = {
            'initial': credentials_data
        }
        formsets = [
            (
                None,
                {
                    'fields': (
                        'remote_access_url',
                        'token',
                    )
                }
            )
        ]
        if self.request.method == 'POST':
            form = AE_2100_CredentialsForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                remote_access_url = form.cleaned_data['remote_access_url']
                token = form.cleaned_data['token']
                dev_info = form.cleaned_data['dev_info']
                credentials_data.update({
                    'remote_access_url': remote_access_url,
                    'token': token
                })
                ac_data.update({
                    'credentials': credentials_data,
                    'dev_info': dev_info
                })
                session_data.update({'acurev_2110': ac_data})
                self.session_data = session_data
                return self.make_redirect(
                    'acurev_2110_summary'
                )
        else:
            form = AE_2100_CredentialsForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Acurev 2110 Gateway Api',
            'submit_value': 'NEXT',
            'submit_name': 'NEXT',
            'step': 'acurev_2110_gateway_options'
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/acurev_2110_credentials.html',
            self._make_conext(context)
        )

    def acurev_2110_summary_step(self):
        session_data = self.session_data
        ac_data = session_data.get('acurev_2110')
        dev_info = ac_data.get('dev_info')
        if not dev_info:
            return self.make_redirect('acurev_2110_gateway_options')

        form_kwargs = {}
        formsets = [
            (
                None,
                {
                    'fields': [
                        'collect_logs',
                    ]
                }
            )
        ]

        if self.request.method == 'POST':
            form = AE_2100_SummaryForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                collect_logs = form.cleaned_data['collect_logs']
                gateway_manager = apps.get_model('x6gateapi.Gateway').objects
                project_id = self.session_data.get('main', {}).get('project')
                gateway, created = gateway_manager.get_or_create(
                    project_id=project_id,
                    sn=dev_info.get('meterSerialNumber'),
                    defaults={
                        'gateway_type': dev_info.get('meterModel'),
                        'name': dev_info.get('meterSerialNumber'),
                        'site': {},
                        'owner': {},
                        'room': {},
                        'ver': dev_info.get('meterHardwareVersion'),
                        'extra_data': {
                            'alarms_enabled': collect_logs,
                        },
                        'secret_extra_data': {
                            'api_client': ac_data.get('credentials', {})
                        },
                    },
                )
                if not created:
                    gateway.gateway_type = dev_info.get('meterModel')
                    gateway.name = dev_info.get('meterSerialNumber')
                    gateway.extra_data.update({
                        'alarms_enabled': collect_logs,
                    })
                    gateway.secret_extra_data.update({
                        'api_client': ac_data.get('credentials', {})
                    })
                    gateway.save()
                self.session_data = {}
                return HttpResponseRedirect(
                    reverse(
                        'admin:x6gateapi_gateway_change',
                        kwargs={'object_id': gateway.id}
                    )
                )
        elif self.request.method == 'GET':
            form = AE_2100_SummaryForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Acurev 2110 Gateway Api Info',
            'step': 'acurev_2110_summary',
            'dev_info': dev_info,
            'submit_value': 'CREATE',
            'submit_name': 'CREATE',
        }
        return TemplateResponse(
            self.request,
            'megedc/x6gateapi/acurev_2110_summary.html',
            self._make_conext(context)
        )

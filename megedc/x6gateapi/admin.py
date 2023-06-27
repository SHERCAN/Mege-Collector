import json
from datetime import datetime
from django import forms
from django_admin_relation_links import AdminChangeLinksMixin
from django.apps import apps
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.options import csrf_protect_m
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.http.response import HttpResponseRedirect
from django.template.exceptions import TemplateSyntaxError
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from megedc.accuenergy.api_client import AccuenergyApiClient
from megedc.emporiaenergy.partner_api import (
    partner_api,
    PartnerApiException,
    PartnerApiResponseException,
)
from megedc.mixers import CeUpDeAtAdminMixser
from megedc.x6gateapi import EE_RESOLUTION_CHOICES
from megedc.x6gateapi.gateway_maker import GatewayMaker
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer


# Fot register Admin classes
_for_register = [
    # (model_name, Admin class)
]


def make_html_json(data):
    response = json.dumps(data, sort_keys=True, indent=4)
    formatter = HtmlFormatter()
    response = highlight(response, JsonLexer(), formatter)
    style = "<style>" + formatter.get_style_defs() + "</style><br>"
    return mark_safe(style + response)


class GatewayAdminForm(forms.ModelForm):

    ee_credentials_host = forms.CharField(
        required=True,
        label='Host'
    )

    ee_credentials_port = forms.IntegerField(
        min_value=1,
        max_value=65535,
        required=True,
        label='port'
    )

    ee_credentials_email = forms.EmailField(
        required=True,
        label='Email'
    )

    ee_credentials_password = forms.CharField(
        widget=forms.PasswordInput,
        label='Password',
        required=False,
    )

    ee_data_resolution = forms.ChoiceField(
        choices=EE_RESOLUTION_CHOICES,
        required=True,
        label='Resolution'
    )

    ac_remote_access_url = forms.URLField(
        required=True,
    )

    ac_token = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'style': 'width:400px;'})
    )

    ac_collect_logs = forms.BooleanField(initial=True, required=False)

    class Meta:
        model = apps.get_model('x6gateapi.gateway')
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            gateway_type = self.instance.gateway_type
            if gateway_type != 'emporia_energy':
                del(self.fields['ee_credentials_host'])
                del(self.fields['ee_credentials_port'])
                del(self.fields['ee_credentials_email'])
                del(self.fields['ee_credentials_password'])
                del(self.fields['ee_data_resolution'])
            else:
                secret_emporia_energy = self.instance.secret_extra_data.get(
                    'emporia_energy', {}
                )
                host = secret_emporia_energy.get('host')
                port = secret_emporia_energy.get('port')
                email = secret_emporia_energy.get('email')
                self.initial['ee_credentials_host'] = host
                self.initial['ee_credentials_port'] = port
                self.initial['ee_credentials_email'] = email

                extra_emporia_energy = self.instance.extra_data.get(
                    'emporia_energy', {}
                )
                resolution = extra_emporia_energy.get('resolution')
                self.initial['ee_data_resolution'] = resolution

            if gateway_type is None or not gateway_type.startswith('AcuRev 2'):
                del(self.fields['ac_remote_access_url'])
                del(self.fields['ac_token'])
                del(self.fields['ac_collect_logs'])
            else:
                remote_access_url = self.instance.secret_extra_data.get(
                    'api_client', {}
                ).get('remote_access_url', '')
                token = self.instance.secret_extra_data.get(
                    'api_client', {}
                ).get('token', '')
                collect_logs = self.instance.extra_data.get(
                    'alarms_enabled', False
                )
                self.initial['ac_remote_access_url'] = remote_access_url
                self.initial['ac_token'] = token
                self.initial['ac_collect_logs'] = collect_logs

    def clean(self):
        cleaned_data = super().clean()
        gateway_type = self.instance.gateway_type
        if gateway_type == 'emporia_energy':
            changed = (
                'ee_credentials_host' in self.changed_data
                or 'ee_credentials_port' in self.changed_data
                or 'ee_credentials_email' in self.changed_data
                or 'ee_credentials_password' in self.changed_data
            )
            if changed:
                host = self.cleaned_data.get('ee_credentials_host', None)
                port = self.cleaned_data.get('ee_credentials_port', None)
                email = self.cleaned_data.get('ee_credentials_email', None)
                password = self.cleaned_data.get(
                    'ee_credentials_password', None
                )
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
        if gateway_type is not None and gateway_type.startswith('AcuRev 2'):
            changed = (
                'ac_token' in self.changed_data
                or 'ac_remote_access_url' in self.changed_data
            )
            if changed:
                token = self.cleaned_data.get('ac_token', None)
                url = self.cleaned_data.get('ac_remote_access_url', None)
                api_client = AccuenergyApiClient(url, token)
                try:
                    dev_info = api_client.get_settings_deviceInfo()
                    cleaned_data['dev_info'] = dev_info
                except Exception as exce:
                    raise ValidationError(
                        str(exce)
                    )
        return cleaned_data

    def save(self, commit=True):
        gateway_type = self.instance.gateway_type
        if gateway_type == 'emporia_energy':
            changed = (
                'ee_credentials_host' in self.changed_data
                or 'ee_credentials_port' in self.changed_data
                or 'ee_credentials_email' in self.changed_data
                or 'ee_credentials_password' in self.changed_data
            )
            if changed:
                host = self.cleaned_data.get('ee_credentials_host', None)
                port = self.cleaned_data.get('ee_credentials_port', None)
                email = self.cleaned_data.get('ee_credentials_email', None)
                password = self.cleaned_data.get(
                    'ee_credentials_password', None
                )
                secret_extra_data = self.instance.secret_extra_data
                secret_ee = secret_extra_data.get('emporia_energy', {})
                secret_ee.update({
                    'host': host,
                    'port': port,
                    'email': email,
                    'password': password
                })
                secret_extra_data.update({
                    'emporia_energy': secret_ee
                })
                self.instance.secret_extra_data = secret_extra_data

            if 'ee_data_resolution' in self.changed_data:
                resolution = self.cleaned_data.get('ee_data_resolution', None)
                extra_data = self.instance.extra_data
                ee_extra = extra_data.get('emporia_energy', {})
                ee_extra.update({
                    'resolution': resolution,
                })
                extra_data.update({
                    'emporia_energy': ee_extra
                })
                self.instance.extra_data = extra_data

        if gateway_type is not None and gateway_type.startswith('AcuRev 2'):
            secret_extra_data = self.instance.secret_extra_data
            extra_data = self.instance.extra_data
            api_client = secret_extra_data.get('api_client')
            if api_client is None:
                api_client = {}
                secret_extra_data['api_client'] = api_client
            if 'ac_token' in self.changed_data:
                api_client.update({'token': self.cleaned_data.get('ac_token')})
            if 'ac_remote_access_url' in self.changed_data:
                api_client.update({'remote_access_url': self.cleaned_data.get(
                    'ac_remote_access_url'
                )})
            if 'ac_collect_logs' in self.changed_data:
                extra_data.update({'alarms_enabled': self.cleaned_data.get(
                    'ac_collect_logs'
                )})
            if 'dev_info' in self.cleaned_data:
                dev_info = self.cleaned_data['dev_info']
                self.instance.gateway_type = dev_info.get('meterModel')
                self.instance.name = dev_info.get('meterSerialNumber')
        return super().save(commit)


class GatewayProjectRelatedFieldListFilter(admin.RelatedFieldListFilter):

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        limit_choices_to = None
        if not request.user.is_superuser:
            limit_choices_to = {
                'client': request.user.megeuser.client
            }
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                limit_choices_to = {
                    'client_id': chgc_client
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to
        )

    def queryset(self, request, queryset):
        queryset = super().queryset(request, queryset)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    project__client_id=chgc_client
                )
        return queryset


class GatewayAdmin(CeUpDeAtAdminMixser,
                   AdminChangeLinksMixin,
                   admin.ModelAdmin):

    class disable_action:

        __name__ = 'Disable'
        short_description = 'Disable selected projects'
        disable_value = False

        def __call__(self, modeladmin, request, queryset):
            queryset.update(enabled=self.disable_value)

    class enable_action(disable_action):

        __name__ = 'Enable'
        short_description = 'Enable selected projects'
        disable_value = True

    form = GatewayAdminForm

    actions = [
        disable_action(),
        enable_action()
    ]

    change_links = [
        'project',
    ]

    changelist_links = [
        'devices',
    ]

    ordering = [
        'name',
    ]

    # fields = (
    #     'sn',
    #     'project_link',
    #     'name',
    #     'ver',
    #     'site_data',
    #     'owner_data',
    #     'room_data',
    #     'time_zone',
    #     'enabled',
    #     'created_at',
    #     'updated_at',
    #     'devices_link',
    #     'export_data',
    #     'removed_at'
    # )

    fieldsets = [
        (
            None,
            {
                'fields': [
                    'sn',
                    'project_link',
                    'name',
                    'ver',
                    'site_data',
                    'owner_data',
                    'room_data',
                    'time_zone',
                    'enabled',
                    'created_at',
                    'updated_at',
                    'devices_link',
                    'export_data',
                    'export_alarms_data',
                ]
            }
        )
    ]

    list_display = [
        'sn',
        'name',
        'project_link',
        'timezone',
        'devices_link',
        'enabled',
    ]

    readonly_fields = [
        'sn',
        'project_link',
        'name',
        'ver',
        'site_data',
        'owner_data',
        'room_data',
        'export_data',
        'export_alarms_data',
    ]

    list_filter = [
        ('project', GatewayProjectRelatedFieldListFilter),
        'enabled'
    ]

    search_fields = (
        'sn',
        'name',
        'ver',
        'project__name',
        'project__client__name',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    project__client_id=chgc_client
                )
        return queryset

    def has_delete_permission(self, request, obj=None):
        return False

    def site_data(self, instance):
        return make_html_json(instance.site)

    def owner_data(self, instance):
        return make_html_json(instance.owner)

    def room_data(self, instance):
        return make_html_json(instance.room)

    def export_data(self, instance):
        link = reverse('admin:data_export_dataexport_changelist')
        return mark_safe(
            '<a href="%s?gateway=%s">link</a>' % (link, instance.id)
        )

    def export_alarms_data(self, instance):
        link = reverse('data_export:rtalarm-export')
        return mark_safe(
            '<a target="_blank" href="%s?gateway=%s">link</a>' % (
                link, instance.id
            )
        )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                'maker/',
                self.admin_site.admin_view(self.gateway_maker_view),
                name="gateway-maker"
            )
        ]
        return my_urls + urls

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url='',
                        extra_context=None):
        if object_id is None:
            return HttpResponseRedirect(
                reverse('admin:gateway-maker')
            )
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context
        )

    @csrf_protect_m
    def gateway_maker_view(self, request):
        maker = GatewayMaker(self, request)
        return maker.response()

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj is not None:
            if obj.gateway_type == 'emporia_energy':
                readonly_fields = readonly_fields.copy()
                readonly_fields.append('ee_data_from_date')
        return readonly_fields

    def ee_data_from_date(self, obj):
        from_date = obj.extra_data.get('emporia_energy', {}).get('from_date')
        return datetime.fromisoformat(from_date) if from_date else None
    ee_data_from_date.__name__ = 'Last get date'

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None:
            gateway_type = obj.gateway_type
            if gateway_type == 'emporia_energy':
                fieldsets = fieldsets.copy()
                fieldsets.extend([(
                    'Emporia Credentials',
                    {
                        'fields': [
                            'ee_credentials_host',
                            'ee_credentials_port',
                            'ee_credentials_email',
                            'ee_credentials_password',
                        ]
                    }
                ), (
                    'Emporia Data',
                    {
                        'fields': [
                            'ee_data_resolution',
                            'ee_data_from_date',
                        ]
                    }
                )])
            is_AcuRev = (
                gateway_type is not None
                and gateway_type.startswith('AcuRev 2')
            )
            if is_AcuRev:
                fieldsets = fieldsets.copy()
                fieldsets.extend([(
                    'AcuRev 2100 data',
                    {
                        'fields': [
                            'ac_remote_access_url',
                            'ac_token',
                            'ac_collect_logs',
                        ]
                    }
                )])
        return fieldsets


_for_register.append(('x6gateapi.gateway', GatewayAdmin))


class DeviceProjectRelatedFieldListFilter(admin.RelatedFieldListFilter):

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        limit_choices_to = None
        if not request.user.is_superuser:
            limit_choices_to = {
                'client': request.user.megeuser.client
            }
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                limit_choices_to = {
                    'client_id': chgc_client
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to
        )

    def queryset(self, request, queryset):
        queryset = super().queryset(request, queryset)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                gateway__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    gateway__project__client_id=chgc_client
                )
        return queryset


class DeviceGatewayRelatedFieldListFilter(admin.RelatedFieldListFilter):

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        limit_choices_to = None
        if not request.user.is_superuser:
            limit_choices_to = {
                'project__client': request.user.megeuser.client
            }
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                limit_choices_to = {
                    'project__client_id': chgc_client
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to
        )

    def queryset(self, request, queryset):
        queryset = super().queryset(request, queryset)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                gateway__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    gateway__project__client_id=chgc_client
                )
        return queryset


class DeviceAdmin(CeUpDeAtAdminMixser,
                  AdminChangeLinksMixin,
                  admin.ModelAdmin):

    class ready_action:

        __name__ = 'Ready'
        short_description = 'Mark devices as ready'
        ready_value = True

        def __call__(self, modeladmin, request, queryset):
            queryset.update(ready=self.ready_value)

    class not_ready_action(ready_action):

        __name__ = 'motReady'
        short_description = 'Unmark devices as ready'
        ready_value = False

    actions = [
        ready_action(),
        not_ready_action()
    ]

    change_links = [
        'gateway',
    ]

    ordering = [
        'channel',
        'id',
    ]

    fields = (
        'gateway_link',
        'channel_id',
        'name',
        'desc',
        'ready',
        'created_at',
        'updated_at',
        'export_data'
    )

    list_display = [
        'channel_id',
        'name',
        'gateway_link',
        'ready',
    ]

    readonly_fields = [
        'gateway_link',
        'channel_id',
        'name',
        'desc',
        'export_data',
        'created_at',
        'updated_at',
    ]

    list_filter = [
        ('gateway__project', DeviceProjectRelatedFieldListFilter),
        ('gateway', DeviceGatewayRelatedFieldListFilter),
        'ready'
    ]

    search_fields = (
        'name',
        'desc',
        'gateway__name',
        'gateway__project__name',
        'gateway__project__client__name',
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def channel_id(self, instance):
        return '%s - %s' % (instance.channel, instance.id)

    def export_data(self, instance):
        link = reverse('admin:data_export_dataexport_changelist')
        return mark_safe(
            '<a href="%s?devices=%s">link</a>' % (link, instance.dev_id)
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                gateway__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    gateway__project__client_id=chgc_client
                )
        return queryset


_for_register.append(('x6gateapi.device', DeviceAdmin))


class AlertAdmin(CeUpDeAtAdminMixser,
                 AdminChangeLinksMixin,
                 admin.ModelAdmin):

    class EmailTestAction:

        __name__ = 'email_test_action'
        short_description = 'Send test'

        def __call__(self, modeladmin, request, queryset):

            for alert in queryset.iterator():
                device = None
                try:
                    device = alert.gateway.devices.filter(
                        channel=alert.device_channel,
                        id=alert.device_id,
                        removed_at__isnull=True,
                    ).get()
                except ObjectDoesNotExist:
                    try:
                        device = alert.gateway.devices.all().first()
                    except ObjectDoesNotExist:
                        pass
                if device is None:
                    modeladmin.message_user(
                        request,
                        'Device not found',
                        messages.ERROR,
                    )
                    return
                rt_alarm = None
                rt_alarm_l = device.alarms.all().order_by('-date_time')[:1]
                for rta in rt_alarm_l:
                    rt_alarm = rta
                    break
                if rt_alarm is None:
                    rtdate = localtime()
                    rt_alarm = apps.get_model('x6gateapi.RTAlarm')(
                        logdt=rtdate.isoformat(),
                        date_time=rtdate,
                        name='TestName',
                        value='80 %',
                        threadhold_value='',
                        device=device
                    )
                try:
                    modeladmin.message_user(
                        request,
                        '%s emails sends' % (alert.send(rt_alarm)),
                        messages.SUCCESS,
                    )
                except TemplateSyntaxError as exce:
                    modeladmin.message_user(
                        request,
                        str(exce),
                        messages.ERROR,
                    )

    actions = [
        EmailTestAction()
    ]

    fields = [
        'name',
        'enabled',
        'gateway',
        'device_channel',
        'device_id',
        'emails',
        # 'from_email',
        'from_email_name',
        'subject_template',
        'msg_template',
        'html_msg_template',
    ]

    list_display = [
        'name',
        'gateway',
        'device_channel',
        'device_id',
        'emails'
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                gateway__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    gateway__project__client_id=chgc_client
                )
        return queryset

    def get_field_queryset(self, db, db_field, request):
        queryset = super().get_field_queryset(db, db_field, request)
        if db_field.name == 'gateway':
            if not request.user.is_superuser:
                queryset = queryset.filter(
                    project__client=request.user.megeuser.client
                )
            else:
                chgc_client = request.session.get('chgc_client')
                if chgc_client:
                    queryset = queryset.filter(
                        project__client_id=chgc_client
                    )
        return queryset

    def delete_model(self, request, obj):
        obj.__class__.objects.filter(pk=obj.pk).update(removed_at=localtime())

    def delete_queryset(self, request, queryset):
        queryset.update(removed_at=localtime())

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['gateway'].label_from_instance = (
            lambda obj: '%s - %s' % (
                obj.project.name,
                (obj.name if obj.name else obj.sn)
            )
        )
        return form


_for_register.append(('x6gateapi.Alert', AlertAdmin))


class RTAlarmAdmin(AdminChangeLinksMixin,
                   admin.ModelAdmin):

    list_display = [
        'logdt',
        'date_time',
        'name',
        'device_link',
        'value',
    ]

    change_links = [
        'device',
    ]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                device__gateway__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    device__gateway__project__client_id=chgc_client
                )
        return queryset.select_related(
            'device'
        )


_for_register.append(('x6gateapi.RTAlarm', RTAlarmAdmin))


for model_name, admin_class in _for_register:
    model = apps.get_model(model_name)
    if not admin.site.is_registered(model):
        admin.site.register(model, admin_class)

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, ngettext
from megedc.data_export.models import DataExport
from megedc.data_export.views import (
    FormDataViewAPIView,
    FormDataUpdateViewAPIView
)
from rangefilter.filters import DateTimeRangeFilterBuilder


class AggregateAttr():

    template = get_template('megedc/de_input.html')

    def __init__(self, attr_name, var_name2, dev_id, can_change):
        self.__name__ = attr_name
        self.short_description = attr_name
        self.var_name2 = var_name2
        self.dev_id = dev_id
        self.can_change = can_change

    def __call__(self, instance):
        val = getattr(instance, self.__name__)
        if self.can_change:
            return mark_safe(self.template.render({
                'val': val if val is not None else '',
                'id': instance.id,
                'name_id': 'de_ed_%s_%s' % (instance.id, self.var_name2),
                'real_var_name': self.var_name2,
                'dev_id': self.dev_id,
            }))
        return val


class ExportDataListFilter(admin.ListFilter):

    title = 'Valid data'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self._model_admin = model_admin
        for param_name in ['valid', 'devices', 'gateway', 'vars', 'discard']:
            self.used_parameters[param_name] = params.pop(param_name, None)

    def has_output(self):
        return True

    def choices(self, changelist):
        return [
            {
                'selected': False,
                'query_string': changelist.get_query_string({'discard': 'f'}),
                'display': 'yes',
            },
            {
                'selected': False,
                'query_string': changelist.get_query_string(
                    {'discard': 't'}
                ),
                'display': 'all',
            }
        ]

    def queryset(self, request, queryset):
        return queryset

    def expected_parameters(self):
        return []


class ExportDataAdmin(admin.ModelAdmin):

    class Media:
        js = ("admin/js/dataexport.js",)

    class discard_action:

        __name__ = 'Discard'
        short_description = 'Discard values'
        discard_value = True

        def __call__(self, modeladmin, request, queryset):
            queryset.update(discard=self.discard_value)

    class not_discard_action(discard_action):

        __name__ = 'motReady'
        short_description = 'Mark values as valid'
        discard_value = False

    actions = [
        not_discard_action(),
        discard_action()
    ]

    list_per_page = 100

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('form_data/', FormDataViewAPIView.as_view()),
            path(
                'form_data/edit/<int:data_id>/<int:dev_id>/<str:var_name>/',
                FormDataUpdateViewAPIView.as_view()
            ),
        ]
        return my_urls + urls

    @property
    def dataexport_manager(self):
        return apps.get_model('data_export.dataexport').objects

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        device_ids = []
        for x in request.GET.get('devices', '').split(','):
            if x:
                device_ids.append(int(x))
        gateway_id = request.GET.get('gateway', None)
        if gateway_id:
            gateway_id = int(gateway_id)
        allow_vars = []
        for x in request.GET.get('vars', '').split(','):
            if x:
                allow_vars.append(x)
        discard = request.GET.get('discard', None)
        return self.dataexport_manager.export_queryset(
            device_ids=device_ids,
            gateway_id=gateway_id,
            vars=allow_vars,
            discard=discard
        )

    def get_fields(self, request, obj=None):
        return [
            'date_time',
        ] + self.get_var_names(request) + [
            'valid'
        ]

    def get_list_display(self, request):
        return [
            'date_time',
        ] + self.get_var_names(request) + [
            'valid'
        ]

    list_display_links = None

    def get_readonly_fields(self, request, obj=None):
        return [
            'date_time',
            'valid',
        ] + self.get_var_names(request)

    def get_list_filter(self, request):
        return [
            ExportDataListFilter,
            ("date_time", DateTimeRangeFilterBuilder())
        ]

    def get_var_names(self, request, ret_all=False):
        if not hasattr(request, 'mege_export_data'):
            device_ids = []
            for x in request.GET.get('devices', '').split(','):
                if x:
                    device_ids.append(int(x))
            gateway_id = request.GET.get('gateway', None)
            discard = request.GET.get('discard', None)
            if gateway_id:
                gateway_id = int(gateway_id)
            allow_vars = []
            for x in request.GET.get('vars', '').split(','):
                if x:
                    allow_vars.append(x)
            gateway_id, var_names = self.dataexport_manager.get_var_names(
                device_ids=device_ids,
                gateway_id=gateway_id,
                vars=allow_vars,
                discard=discard
            )
            final_vars_names = []
            can_change = self.has_change_permission(request)
            for dev_id in var_names:
                for var_name, var_name2 in var_names[dev_id]:
                    setattr(self, var_name, AggregateAttr(
                        var_name, var_name2, dev_id, can_change
                    ))
                    final_vars_names.append(var_name)

            request.mege_export_data = {
                'vars_names': final_vars_names,
                'gateway_id': gateway_id,
                'devices_ids': var_names.keys(),
            }

        if not ret_all:
            return request.mege_export_data['vars_names']

    def get_changelist_instance(self, request):
        instance = super().get_changelist_instance(request)
        gw_id = request.mege_export_data.get('gateway_id')
        devices_ids = request.mege_export_data.get('devices_ids')

        title_parts = []

        if gw_id:
            gateway = apps.get_model('x6gateapi.gateway').objects.get(pk=gw_id)
            project = gateway.project
            client = project.client
            title_parts.append(client.name)
            title_parts.append(project.name)
            title_parts.append(gateway.name)

            devices = apps.get_model(
                'x6gateapi.device'
            ).objects.filter(dev_id__in=devices_ids).values_list('name')

            title_parts.append('[%s]' % (", ".join(
                [x[0] for x in devices]
            )))
        else:
            title_parts.append('Select values')

        instance.title = ' > '.join(title_parts)
        return instance

    def valid(self, instance):
        return not instance.discard

    valid.boolean = True

    @admin.options.csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        if not self.get_var_names(request):
            if not self.has_view_or_change_permission(request):
                raise PermissionDenied

            cl = self.get_changelist_instance(request)

            FormSet = self.get_changelist_formset(request)
            formset = cl.formset = FormSet(queryset=cl.result_list)
            if formset:
                media = self.media + formset.media
            else:
                media = self.media
            actions = self.get_actions(request)
            if actions:
                action_form = self.action_form(auto_id=None)
                action_form.fields['action'].choices = self.get_action_choices(
                    request
                )
                media += action_form.media
            else:
                action_form = None

            selection_note_all = ngettext(
                '%(total_count)s selected',
                'All %(total_count)s selected',
                cl.result_count
            )
            opts = self.model._meta

            clients_qs = apps.get_model(
                'general.client'
            ).objects.all()
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                clients_qs = clients_qs.filter(id=chgc_client)
            elif request.user.megeuser.client:
                clients_qs = clients_qs.filter(
                    id=request.user.megeuser.client.id
                )
            clients = clients_qs.order_by('name').values_list('id', 'name')

            context = {
                **self.admin_site.each_context(request),
                'module_name': str(opts.verbose_name_plural),
                'selection_note': _('0 of %(cnt)s selected') % {
                    'cnt': len(cl.result_list)
                },
                'selection_note_all': selection_note_all % {
                    'total_count': cl.result_count
                },
                'title': cl.title,
                'subtitle': None,
                'is_popup': cl.is_popup,
                'to_field': cl.to_field,
                'cl': cl,
                'media': media,
                'has_add_permission': self.has_add_permission(request),
                'opts': cl.opts,
                'action_form': action_form,
                'actions_on_top': self.actions_on_top,
                'actions_on_bottom': self.actions_on_bottom,
                'actions_selection_counter': self.actions_selection_counter,
                'preserved_filters': self.get_preserved_filters(request),
                'clients': clients,
                **(extra_context or {}),
            }
            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                'megedc/export_form.html',
                context
            )
        return super().changelist_view(request, extra_context)


admin.site.register(DataExport, ExportDataAdmin)

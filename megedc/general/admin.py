from copy import deepcopy
from django_admin_relation_links import AdminChangeLinksMixin
from django_json_widget.widgets import JSONEditorWidget
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, JSONField
from django.db.transaction import atomic
from django.forms import Form, ModelForm
from django.forms.fields import CharField, BooleanField
from django.forms.widgets import (
    HiddenInput, MultipleHiddenInput, SelectMultiple, Select
)
from django_jsonform.widgets import JSONFormWidget
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from megedc.billing.invoice_makers import InvoiceMakers
from megedc.mixers import CeUpDeAtAdminMixser
from megedc.utils import bool_from_str


# Fot register Admin classes
_for_register = [
    # (model_name, Admin class)
]


class CurrencyAdmin(admin.ModelAdmin):

    def has_delete_permission(self, request, obj=None):
        return False


_for_register.append(('general.currency', CurrencyAdmin))


class ClientAdminModelForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if 'invoice_makers_allowed' in self.fields:
            self.fields['invoice_makers_allowed'].widget = SelectMultiple(
                choices=InvoiceMakers.choices(add_none=False)
            )
            if instance is not None:
                self.fields[
                    'invoice_makers_allowed'
                ].initial = instance.invoice_makers_allowed
        if 'invoice_maker' in self.fields:
            choices = InvoiceMakers.choices(add_none=False)
            self.fields['invoice_maker'].widget = Select(
                choices=choices
            )

    class Meta:
        model = apps.get_model('general.client')
        fields = '__all__'


class ClientAdmin(AdminChangeLinksMixin, admin.ModelAdmin):

    form = ClientAdminModelForm

    formfield_overrides = {
        JSONField: {'widget': JSONEditorWidget},
    }

    fieldsets = (
        (None, {
            'fields': (
                'name',
                'desc',
                'time_zone',
                'invoice_tax',
                'currency_model',
                'projects_link'
            )
        }),
        ('Invoice', {
            'classes': ('collapse',),
            'fields': (
                'tax_id',
                'invoice_id_generator',
                'invoice_id_generator_kwargs',
                'invoice_maker',
                'invoice_maker_kwargs',
                'invoice_makers_allowed',
                'invoice_makers_allowed_selected',
            ),
        }),
    )

    ordering = (
        'name',
    )

    changelist_links = [
        'projects',
    ]

    list_display = (
        'name',
        'timezone',
        'projects_link',
    )

    search_fields = (
        'name',
        'desc',
    )

    readonly_fields = [
        'invoice_makers_allowed_selected'
    ]

    def get_readonly_fields(self, request, obj):
        fields = list(deepcopy(super().get_readonly_fields(request, obj)))
        if not request.user.is_superuser:
            fields.append(
                'name'
            )
        return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(deepcopy(super().get_fieldsets(request, obj)))
        if not request.user.is_superuser:
            fields = list(fieldsets[0][1]['fields'])
            fields.remove(
                'projects_link'
            )
            fieldsets[0][1]['fields'] = fields
        return fieldsets

    def get_list_display(self, request):
        list_display = list(deepcopy(super().get_list_display(request)))
        if not request.user.is_superuser:
            list_display.remove(
                'projects_link'
            )
        return list_display

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(id=request.user.megeuser.client.id)
        return queryset

    def has_delete_permission(self, request, obj=None):
        return False

    def invoice_makers_allowed_selected(self, obj=None):
        if obj is not None:
            return ', '.join([
                InvoiceMakers.get(x).name for x in obj.invoice_makers_allowed
            ])
        return '-'


_for_register.append(('general.client', ClientAdmin))


class ProjectDeleteActionConfirm:

    template_name = 'general/admin/project_delete_confirm.html'

    __name__ = 'delete'

    short_description = 'Delete projects'

    class ItemsFormForm(Form):
        _selected_action = CharField(widget=MultipleHiddenInput)
        select_across = BooleanField(widget=HiddenInput)

    def __call__(self, modeladmin, request, queryset):
        queryset = self.get_queryset(modeladmin, request, queryset)
        if 'action_confirm' not in request.POST:
            return TemplateResponse(
                request=request,
                template=self.template_name,
                context=self.get_context(modeladmin, request, queryset),
            )
        else:
            counrt = queryset.count()
            with atomic():
                apps.get_model('x6gateapi.gateway').objects.filter(
                    removed_at__isnull=True,
                    project__in=queryset
                ).update(removed_at=localtime())
                apps.get_model('x6gateapi.device').objects.filter(
                    removed_at__isnull=True,
                    gateway__project__in=queryset
                ).update(removed_at=localtime())
                apps.get_model('x6gateapi.rtdata').objects.filter(
                    removed_at__isnull=True,
                    gateway__project__in=queryset
                ).update(removed_at=localtime())
                apps.get_model('x6gateapi.DataNone').objects.filter(
                    removed_at__isnull=True,
                    device__gateway__project__in=queryset,
                ).update(removed_at=localtime())
                apps.get_model('x6gateapi.trendlogdata').objects.filter(
                    removed_at__isnull=True,
                    device__gateway__project__in=queryset,
                ).update(removed_at=localtime())
                local_model = apps.get_model('x6gateapi.local')
                local_qs = local_model.objects.filter(
                    removed_at__isnull=True,
                    project__in=queryset,
                )
                local_admin = self.admin_site._registry.get(local_model)
                local_admin.delete_queryset(request, local_qs)
                queryset.update(removed_at=localtime())

            modeladmin.message_user(
                request,
                '%s projects removed' % (counrt),
                messages.SUCCESS,
            )

    def get_queryset(self, modeladmin, request, queryset):
        return queryset

    def get_context(self, modeladmin, request, queryset):
        select_across = request.POST.get('select_across')
        selected_action = None
        if not select_across:
            selected_action = queryset.values_list('uuid', flat=True)
        else:
            selected_action = queryset[
                0:modeladmin.list_per_page
            ].values_list('uuid', flat=True)

        summary = []

        for project in queryset.iterator():
            gateways_qs = project.gateways.all().filter(
                removed_at__isnull=True
            )
            devices_qs = apps.get_model('x6gateapi.device').objects.filter(
                removed_at__isnull=True,
                gateway__project=project
            )
            rtdata_qs = apps.get_model('x6gateapi.rtdata').objects.filter(
                removed_at__isnull=True,
                gateway__project=project
            )
            datanode_qs = apps.get_model('x6gateapi.DataNone').objects.filter(
                removed_at__isnull=True,
                device__gateway__project=project,
                data__gateway__project=project,
            )
            trnds_qs = apps.get_model('x6gateapi.trendlogdata').objects.filter(
                removed_at__isnull=True,
                device__gateway__project=project,
            )
            p_sum = {
                'name': project.name,
                'gateways_count': gateways_qs.count(),
                'devices_count': devices_qs.count(),
                'rtdata_count': rtdata_qs.count(),
                'datanode_count': datanode_qs.count(),
                'trnds_count': trnds_qs.count(),
            }
            summary.append(p_sum)

        context = {
            **modeladmin.admin_site.each_context(request),
            'action_desc': self.short_description,
            'action_name': request.POST['action'],
            'summary': summary,
            'form': self.ItemsFormForm(
                initial={
                    '_selected_action': selected_action,
                    'select_across': select_across
                }
            )
        }
        return context


class ProjectAdmin(CeUpDeAtAdminMixser,
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

    ordering = [
        'name',
    ]

    actions = [
        disable_action(),
        enable_action(),
        ProjectDeleteActionConfirm()
    ]

    change_links = [
        'client',
    ]

    changelist_links = [
        'gateways',
    ]

    fields = [
        'uuid',
        'client',
        'name',
        'desc',
        'time_zone',
        'x6gate_gateway_config',
        'accuenergy_post_channel_url',
        'enabled',
        'gateways_link',
        'removed_at',
        'created_at',
        'updated_at',
    ]

    list_display = (
        'name',
        'client_link',
        'timezone',
        'gateways_link',
        'enabled',
    )

    readonly_fields = [
        'uuid',
        'x6gate_gateway_config',
        'accuenergy_post_channel_url',
    ]

    search_fields = (
        'name',
        'desc',
        'client__name',
    )

    list_filter = [
        'enabled'
    ]

    def __init__(self, *args, **kwargs):
        self.__request = None
        super().__init__(*args, **kwargs)

    def get_fields(self, request, obj=None):
        self.__request = request
        return super().get_fields(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(client=request.user.megeuser.client)
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(client_id=chgc_client)
        return queryset.select_related('client')

    def has_delete_permission(self, request, obj=None):
        return False

    def x6gate_gateway_config(self, obj):
        data = [
            ('Upload address', self.__request.get_host()),
            ('Upload port', self.__request.get_port()),
            ('Server path', '/'.join([
                settings.MEGEDC_URL_PATH,
                'x6gateapi',
                str(obj.uuid)
            ])),
            ('file type', 'json'),
        ]
        out_put = []
        for attr, value in data:
            out_put.append('<b>%s:</b> %s' % (attr, value))
        return format_html('<br/>'.join(out_put))

    def accuenergy_post_channel_url(self, obj):
        return self.__request.build_absolute_uri(
            reverse('accuenergy:post-channel', kwargs={
                'project_uuid': obj.uuid
            })
        )


_for_register.append(('general.project', ProjectAdmin))


class MegeUserInline(admin.StackedInline):
    model = apps.get_model('general.megeuser')
    can_delete = False
    verbose_name_plural = 'user'


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (MegeUserInline,)


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class CustomerAdminModelForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        im_allowed = None
        if instance is not None:
            im_allowed = instance.client.invoice_makers_allowed
        if 'invoice_maker' in self.fields:
            choices = InvoiceMakers.choices(im_allowed)
            self.fields['invoice_maker'].widget = Select(
                choices=choices
            )

    class Meta:
        model = apps.get_model('general.Customer')
        fields = '__all__'


class CustomerAdmin(CeUpDeAtAdminMixser, admin.ModelAdmin):

    form = CustomerAdminModelForm

    formfield_overrides = {
        JSONField: {'widget': JSONEditorWidget},
    }

    fieldsets = (
        (None, {
            'fields': (
                'client',
                'is_invoice_header',
                'name',
                'desc',
                'legal_id',
                'addess',
                'phones',
                'emails',
                'invoice_tax',
            )
        }),
        ('Invoice', {
            'classes': ('collapse',),
            'fields': (
                'tax_id',
                'invoice_id_generator',
                'invoice_id_generator_kwargs',
                'invoice_maker',
                'invoice_maker_kwargs',
            ),
        }),
        ('Dates', {
            'classes': ('collapse',),
            'fields': (
                'created_at',
                'updated_at',
                'removed_at',
            ),
        }),
    )

    ordering = [
        'name',
    ]

    list_display = [
        'name',
        'desc',
    ]

    search_fields = [
        'name',
        'desc',
        'addess',
        'emails',
    ]

    readonly_fields = [
        'client'
    ]

    list_filter = [
        'is_invoice_header'
    ]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['emails'].widget.attrs['style'] = 'width: 610px;'
        form.base_fields['phones'].widget.attrs['style'] = 'width: 610px'
        return form

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(client=request.user.megeuser.client)
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(client_id=chgc_client)
        return queryset

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj=obj))
        if not request.user.is_superuser:
            fields.remove('client')
        return fields

    def get_readonly_fields(self, request, obj):
        fields = list(super().get_readonly_fields(request, obj))
        if request.user.is_superuser and obj is None:
            fields.remove('client')
        return fields

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.client = request.user.megeuser.client
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        with atomic():
            rental_qs = obj.rentals.all().filter(removed_at__isnull=True)
            rental_admin = self.admin_site._registry.get(
                apps.get_model('general.rental')
            )
            rental_admin.delete_queryset(request, rental_qs)
            obj.__class__.objects.filter(pk=obj.pk).update(
                removed_at=localtime()
            )

    def delete_queryset(self, request, queryset):
        with atomic():
            rental_model = apps.get_model('general.rental')
            rental_qs = rental_model.objects.filter(
                removed_at__isnull=True,
                customer__in=queryset
            )
            rental_admin = self.admin_site._registry.get(rental_model)
            rental_admin.delete_queryset(request, rental_qs)
            queryset.update(removed_at=localtime())


_for_register.append(('general.customer', CustomerAdmin))


class UnitCostAdmin(CeUpDeAtAdminMixser, admin.ModelAdmin):

    ordering = [
        'name',
    ]

    fields = [
        'client',
        'name',
        'desc',
        'invoice_item_format',
        'unit',
        'value',
        'created_at',
        'updated_at',
        'removed_at',
    ]

    list_display = [
        'name',
        'unit',
        'value'
    ]

    search_fields = [
        'name',
        'unit',
    ]

    readonly_fields = [
        'client'
    ]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        currency = None
        try:
            if obj:
                currency = str(obj.client.currency_model)
            elif request.user.megeuser is not None:
                if request.user.megeuser.client is not None:
                    currency = str(request.user.megeuser.client.currency_model)
        except ObjectDoesNotExist:
            pass
        if currency:
            form.base_fields['value'].label = currency
        return form

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(client=request.user.megeuser.client)
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(client_id=chgc_client)
        return queryset

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj=obj))
        chgc_client = request.session.get('chgc_client')
        if not request.user.is_superuser or chgc_client:
            fields.remove('client')
        return fields

    def get_readonly_fields(self, request, obj):
        fields = list(super().get_readonly_fields(request, obj))
        if request.user.is_superuser and obj is None:
            fields.remove('client')
        return fields

    def save_model(self, request, obj, form, change):
        if obj.client is None:
            if not request.user.is_superuser:
                obj.client = request.user.megeuser.client
            else:
                chgc_client = request.session.get('chgc_client')
                obj.client_id = chgc_client
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        with atomic():
            measure_qs = obj.measures.all().filter(removed_at__isnull=True)
            measure_admin = self.admin_site._registry.get(
                apps.get_model('x6gateapi.measure')
            )
            measure_admin.delete_queryset(request, measure_qs)
            obj.__class__.objects.filter(pk=obj.pk).update(
                removed_at=localtime()
            )

    def delete_queryset(self, request, queryset):
        with atomic():
            measure_model = apps.get_model('x6gateapi.measure')
            measure_qs = measure_model.objects.filter(
                removed_at__isnull=True,
                unit_cost__in=queryset,
            )
            measure_admin = self.admin_site._registry.get(measure_model)
            measure_admin.delete_queryset(request, measure_qs)
            queryset.update(removed_at=localtime())


_for_register.append(('general.unitcost', UnitCostAdmin))


class ProjectRelatedFieldListFilter(admin.RelatedFieldListFilter):

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
                client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(project__client_id=chgc_client)
        return queryset


class LocalAdmin(CeUpDeAtAdminMixser, admin.ModelAdmin):

    formfield_overrides = {
        JSONField: {'widget': JSONFormWidget({
            'type': 'dict',
            'keys': {
                'tower': {
                    'type': 'string'
                },
                'floor': {
                    'type': 'string'
                },
                'meter': {
                    'type': 'string',
                }
            }
        })},
    }

    ordering = [
        'name',
    ]

    fields = [
        'project',
        'name',
        'desc',
        'extra',
        'created_at',
        'updated_at',
        'removed_at',
    ]

    list_display = [
        'name',
        'desc',
        'project'
    ]

    search_fields = [
        'name',
        'desc',
    ]

    list_filter = [
        ('project', ProjectRelatedFieldListFilter)
    ]

    def get_field_queryset(self, db, db_field, request):
        queryset = super().get_field_queryset(db, db_field, request)
        if db_field.name == 'project':
            if not request.user.is_superuser:
                queryset = queryset.filter(
                    client=request.user.megeuser.client
                )
            else:
                chgc_client = request.session.get('chgc_client')
                if chgc_client:
                    queryset = queryset.filter(client_id=chgc_client)
        return queryset

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('project')
        if not request.user.is_superuser:
            queryset = queryset.filter(
                project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(project__client_id=chgc_client)
        return queryset

    def get_readonly_fields(self, request, obj):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append('project')
        return fields

    def delete_model(self, request, obj):
        with atomic():
            measure_qs = obj.measures.all().filter(removed_at__isnull=True)
            measure_admin = self.admin_site._registry.get(
                apps.get_model('x6gateapi.measure')
            )
            measure_admin.delete_queryset(request, measure_qs)
            rental_qs = obj.rentals.all().filter(removed_at__isnull=True)
            rental_admin = self.admin_site._registry.get(
                apps.get_model('general.rental')
            )
            rental_admin.delete_queryset(request, rental_qs)
            obj.__class__.objects.filter(pk=obj.pk).update(
                removed_at=localtime()
            )

    def delete_queryset(self, request, queryset):
        with atomic():
            measure_model = apps.get_model('x6gateapi.measure')
            measure_qs = measure_model.objects.filter(
                removed_at__isnull=True,
                local__in=queryset
            )
            measure_admin = self.admin_site._registry.get(measure_model)
            measure_admin.delete_queryset(request, measure_qs)
            rental_model = apps.get_model('general.rental')
            rental_qs = rental_model.objects.filter(
                removed_at__isnull=True,
                local__in=queryset
            )
            rental_admin = self.admin_site._registry.get(rental_model)
            rental_admin.delete_queryset(request, rental_qs)
            queryset.update(removed_at=localtime())


_for_register.append(('general.local', LocalAdmin))


class CustomerLocalRelatedFieldListFilter(admin.RelatedFieldListFilter):

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        limit_choices_to = None
        if not request.user.is_superuser:
            limit_choices_to = {
                'project__client': request.user.megeuser.client,
                'removed_at__isnull': True
            }
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                limit_choices_to = {
                    'project__client_id': chgc_client,
                    'removed_at__isnull': True
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to
        )


class CustomerRelatedFieldListFilter(admin.RelatedFieldListFilter):

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        limit_choices_to = None
        if not request.user.is_superuser:
            limit_choices_to = {
                'client': request.user.megeuser.client,
                'removed_at__isnull': True
            }
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                limit_choices_to = {
                    'client_id': chgc_client,
                    'removed_at__isnull': True
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to,
        )


class FinishedFilter(admin.ListFilter):

    title = 'Show finished'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        # self._model_admin = model_admin
        self.used_parameters['finished'] = params.pop('finished', 'f')

    def has_output(self):
        return True

    def choices(self, changelist):
        finished = bool_from_str(self.used_parameters['finished'])
        return [
            {
                'selected': finished,
                'query_string': changelist.get_query_string({'finished': 't'}),
                'display': 'yes',
            },
            {
                'selected': not finished,
                'query_string': changelist.get_query_string({
                    'finished': None
                }),
                'display': 'no',
            },
        ]

    def queryset(self, request, queryset):
        if not bool_from_str(self.used_parameters['finished']):
            return queryset.filter(
                Q(end_at__isnull=True) | Q(end_at__gt=localtime())
            )
        return queryset

    def expected_parameters(self):
        return ['finished']


class RentalAdmin(CeUpDeAtAdminMixser, admin.ModelAdmin):

    ordering = [
        'local__name',
    ]

    list_filter = [
        FinishedFilter,
        ('local', CustomerLocalRelatedFieldListFilter),
        ('customer', CustomerRelatedFieldListFilter),
    ]

    list_display = [
        'local',
        'customer',
        'start_at',
    ]

    fields = [
        'local',
        'customer',
        'start_at',
        'end_at',
        'created_at',
        'updated_at',
        'removed_at',
    ]

    readonly_fields = [
        'local',
        'customer',
        'start_at',
        'end_at',
    ]

    def get_field_queryset(self, db, db_field, request):
        queryset = super().get_field_queryset(db, db_field, request)
        if not request.user.is_superuser:
            if db_field.name == 'customer':
                queryset = queryset.filter(
                    client=request.user.megeuser.client
                )
            elif db_field.name == 'local':
                queryset = queryset.filter(
                    project__client=request.user.megeuser.client
                )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                if db_field.name == 'customer':
                    queryset = queryset.filter(
                        client_id=chgc_client
                    )
                elif db_field.name == 'local':
                    queryset = queryset.filter(
                        project__client_id=chgc_client
                    )
        return queryset

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'local',
            'customer'
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(
                local__project__client=request.user.megeuser.client,
                customer__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    local__project__client_id=chgc_client,
                    customer__client_id=chgc_client,
                )
        return queryset

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj=obj))
        if obj is None:
            fields.remove('end_at')
        return fields

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if bool_from_str(request.GET.get('finished', 'f')):
            return list_display + ['end_at']
        return list_display

    def get_readonly_fields(self, request, obj):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            if obj.end_at is None:
                fields.remove('end_at')
        else:
            fields.remove('local')
            fields.remove('customer')
            fields.remove('start_at')
        return fields

    def delete_model(self, request, obj):
        obj.__class__.objects.filter(pk=obj.pk).update(removed_at=localtime())

    def delete_queryset(self, request, queryset):
        queryset.update(removed_at=localtime())


_for_register.append(('general.rental', RentalAdmin))


class MeasureProjectRelatedFieldListFilter(admin.RelatedFieldListFilter):

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
                local__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    local__project__client_id=chgc_client
                )
        return queryset


class MeasureLocalRelatedFieldListFilter(admin.RelatedFieldListFilter):

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
                    'project__client_id': chgc_client,
                    'removed_at__isnull': True
                }
        return field.get_choices(
            include_blank=False,
            ordering=ordering,
            limit_choices_to=limit_choices_to
        )


class MeasureAdmin(CeUpDeAtAdminMixser, admin.ModelAdmin):

    formfield_overrides = {
        JSONField: {'widget': JSONEditorWidget},
    }

    ordering = [
        'name',
    ]

    search_fields = [
        'name',
        'local__name',
        'var_name',
        'desc'
    ]

    list_display = [
        'name',
        'local',
        'var_name',
    ]

    fields = [
        'name',
        'desc',
        'local',
        'var_name',
        'calculator',
        'calculator_args',
        'calculator_kwargs',
        'unit_cost',
        'created_at',
        'updated_at',
        'removed_at',
    ]

    list_filter = [
        ('local__project', MeasureProjectRelatedFieldListFilter),
        ('local', MeasureLocalRelatedFieldListFilter)
    ]

    allow_export_link = [
        'PLZR_OCCUPATION_AA',
        'PLZR_CONSUMOTD_AA'
    ]

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj).copy()
        if obj is not None:
            if obj.calculator in self.allow_export_link:
                fields.append('export_link')
        return fields

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj).copy()
        if obj is not None:
            if obj.calculator in self.allow_export_link:
                fields.append('export_link')
        return fields

    def get_field_queryset(self, db, db_field, request):
        queryset = super().get_field_queryset(db, db_field, request)
        if not request.user.is_superuser:
            if db_field.name == 'local':
                queryset = queryset.filter(
                    project__client=request.user.megeuser.client
                )
            elif db_field.name == 'unit_cost':
                queryset = queryset.filter(
                    client=request.user.megeuser.client
                )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                if db_field.name == 'local':
                    queryset = queryset.filter(
                        project__client_id=chgc_client
                    )
                elif db_field.name == 'unit_cost':
                    queryset = queryset.filter(
                        client_id=chgc_client
                    )
        return queryset

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'local',
        ).filter(removed_at__isnull=True)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                local__project__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    local__project__client_id=chgc_client
                )
        return queryset

    def delete_model(self, request, obj):
        obj.__class__.objects.filter(pk=obj.pk).update(removed_at=localtime())

    def delete_queryset(self, request, queryset):
        queryset.update(removed_at=localtime())

    def export_link(self, obj):
        if obj is not None:
            url = reverse(
                'data_export:measure-calc-export',
                kwargs={'pk': obj.id}
            )
            return mark_safe('<a target="_blank" href="%s">%s</a>' % (
                url,
                url
            ))
        return '-'


_for_register.append(('x6gateapi.measure', MeasureAdmin))


for model_name, admin_class in _for_register:
    model = apps.get_model(model_name)
    if not admin.site.is_registered(model):
        admin.site.register(model, admin_class)

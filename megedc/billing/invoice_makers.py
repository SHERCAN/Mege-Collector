from calendar import month_name
from datetime import datetime, timedelta
from django import forms
from django.apps import apps
from django.conf import settings
from django.contrib.admin import widgets
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.timezone import localtime
from megedc.authentication import TokenLowerAuthentication
from megedc.utils import full_reverse
from uuid import uuid4


class DatesForm(forms.Form):

    start_date = forms.DateTimeField(
        widget=widgets.AdminDateWidget(),
        required=True
    )

    end_date = forms.DateTimeField(
        widget=widgets.AdminDateWidget(),
        required=True
    )

    def clean_end_date(self):
        end_date = self.cleaned_data['end_date']
        start_date = self.cleaned_data['start_date']
        if start_date >= end_date:
            raise ValidationError('Must be higher than start date')
        return end_date


class InvoiceMakerBase():

    kwargs_form = None

    def kwargs_form_kwargs(self):
        return {}

    def kwargs_formsets(self):
        return []

    def kwargs_form_process(self, form):
        return form.cleaned_data

    @property
    def invoice_model(self):
        return apps.get_model('billing.invoice')

    @property
    def invoice_manager(self):
        return self.invoice_model.objects

    @property
    def auth_token(self):
        user_model = get_user_model()
        user_manager = get_user_model()._default_manager
        user = None
        try:
            kwargs = {user_model.USERNAME_FIELD: 'mege_query_billing'}
            user = user_manager.get(**kwargs)
        except ObjectDoesNotExist:
            user = user_manager.create_user('mege_query_billing')
        if not user.is_active:
            user.is_active = True
            user.save()
        if not user.has_perm('billing.view_invoice'):
            ct_manager = apps.get_model('contenttypes.ContentType').objects
            content_type = ct_manager.get_for_model(self.invoice_model)
            permission_manager = apps.get_model('auth.Permission').objects
            permission = permission_manager.get(
                codename='view_invoice',
                content_type=content_type,
            )
            user.user_permissions.add(permission)
        auth_token = None
        try:
            auth_token = user.auth_token
        except ObjectDoesNotExist:
            token_model = apps.get_model('authtoken.Token')
            auth_token = token_model(user=user)
            auth_token.save()
        return auth_token.key

    @property
    def authorization(self):
        return '%s %s' % (TokenLowerAuthentication.keyword, self.auth_token)

    def invoice_create(self, *args, **kwargs):
        return self.invoice_manager.create(*args, **kwargs)

    def jasper_url(self):
        return (
            settings.JASPERSERVER_URL
            + '/rest_v2/reports/'
            + settings.MEGEDC_JASPER_INVOICE_REPORT_PATH.get(self.id)
            + '.pdf'
        )

    def jasper_params(self, invoice_pk, preview):
        ret = {
            'data_url': full_reverse(
                'billing:get-invoice-data2', args=[invoice_pk]
            ),
            'preview': 'true' if preview else 'false',
            'auth_token': self.authorization
        }
        return ret

    def jasper_headers(self):
        return None

    dates_from = DatesForm

    def get_date_form_kwargs(self, request, dates_data):
        return {
            'initial': dates_data
        }

    def get_dates(self, request, form, header=None):
        return {
            'start_date': form.cleaned_data['start_date'].isoformat(),
            'end_date': form.cleaned_data['end_date'].isoformat(),
        }

    def get_date_formsets(self, request):
        return [
            (
                None,
                {
                    'fields': (
                        'start_date',
                        'end_date'
                    )
                }
            )
        ]


class PlazaRealInvoiceMaker(InvoiceMakerBase):

    id = 'PLAZA_REAL'
    name = 'Plaza Real'
    version = '1.0'

    preview_list_fields = [
        'p_items',
        'p_tax_total',
        'p_total',
    ]

    def p_items(self, data):
        return len(data.get('items', []))

    p_items.name = "Número de items"

    def p_sub_total(self, data):
        return '%.2f' % data.get('sub_total', 0)

    p_sub_total.name = "Subtotal"

    def p_tax_total(self, data):
        return '%.2f' % data.get('tax_total', 0)

    p_tax_total.name = "Tax"

    def p_total(self, data):
        return '%.2f' % data.get('total', 0)

    p_total.name = "Total"

    def __call__(self, customer, **kwargs):
        invoices = {}
        customer_header = kwargs['header']
        rental_data = kwargs['rental_data']
        preview = kwargs.get('preview', False)
        invoice_id = customer_header.next_invoice_id
        date_time = localtime()
        invoice_id = str(uuid4())
        if not preview:
            invoice_id = customer_header.next_invoice_id
        items = []
        invoice = {
            'version': self.version,
            'maker_id': self.id,
            'maker_name': self.name,
            'generator_id': customer_header.invoice_id_generator,
            'invoice_id': invoice_id,
            'datetime': date_time.isoformat(),
            'date': date_time.strftime('%Y-%m-%d'),
            'time': date_time.strftime('%H:%M'),
            'currency': {
                'name': customer_header.client.currency_model.name,
                'symbol': customer_header.client.currency_model.synbol
            },
            'tax': customer.invoicetax,
            'header': {
                'id': customer_header.id,
                'legal_id': customer_header.legal_id,
                'name': customer_header.name,
                'address': customer_header.addess,
                'phones': ', '.join(customer_header.phones),
                'tax_id': customer_header.invoicetaxid
            },
            'customer': {
                'legal_id': customer.legal_id,
                'name': customer.name
            },
            'items': items
        }
        invoices[invoice_id] = invoice
        total_sub_total = 0
        for rental_id, measures_data in rental_data:
            for measure_id, g_result in measures_data:
                measure = apps.get_model('x6gateapi.Measure').objects.get(
                    id=measure_id
                )
                if not g_result.get('ok', False):
                    continue
                result = g_result['data']
                amount = result.get('result', 0.0)
                unit_value = measure.unit_cost.value
                sub_total = amount * unit_value
                total_sub_total += sub_total
                items.append({
                    'amount': amount,
                    'amount_unit': measure.unit_cost.unit,
                    'desc': measure.make_invoice_item_desc(result),
                    'unit_value': measure.unit_cost.value,
                    'sub_total': sub_total
                })

        invoice['sub_total'] = total_sub_total
        invoice['tax_total'] = (customer.invoicetax * total_sub_total) / 100
        invoice['total'] = total_sub_total + invoice['tax_total']

        ret = invoices
        if not preview:
            ret2 = {}
            for invoice_id, invoice_data in invoices.items():
                ret2[invoice_id] = self.invoice_create(
                    data=invoice_data,
                    invoice_id=invoice_id,
                    customer=customer
                )
            return ret2
        return ret


class BusinessParkInvoiceMakerKwargsForm(forms.Form):

    pecim = forms.FloatField(required=True, min_value=0.0, initial=0.0)
    cadmm = forms.FloatField(required=True, min_value=0.0, initial=0.0)
    enable_cac = forms.BooleanField(required=False, initial=True)
    cac_total = forms.FloatField(
        required=False, min_value=0.0, initial=0.0
    )


class BPDatesForm(forms.Form):

    month = forms.IntegerField(
        widget=forms.Select(choices=[
            (x, month_name[x]) for x in list(range(1, 12))
        ]),
        required=True
    )

    year = forms.IntegerField(
        widget=forms.Select(),
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['year'].widget.choices = [
            (x, x) for x in list(
                range(datetime.now().year - 5, datetime.now().year + 2)
            )
        ]


class BusinessParkInvoiceMaker(InvoiceMakerBase):

    id = 'BUSINESS_PARK'
    name = 'Business Park'
    version = '1.0'

    kwargs_form = BusinessParkInvoiceMakerKwargsForm

    dates_from = BPDatesForm

    def get_date_form_kwargs(self, request, dates_data):
        month = None
        year = None
        if dates_data.get('start_date') is None:
            now_date = datetime.now()
            month = now_date.month
            year = now_date.year
        else:
            c_date = datetime.fromisoformat(dates_data.get('start_date'))
            month = c_date.month
            year = c_date.month
        return {
            'initial': {
                'month': month,
                'year': year
            }
        }

    def get_dates(self, request, form, header=None):
        month = form.cleaned_data['month']
        year = form.cleaned_data['year']
        start_date = datetime(
            day=1,
            month=month,
            year=year,
            tzinfo=header.client.timezone
        )
        end_date = datetime(
            day=1,
            month=(month+1 if month < 12 else 1),
            year=(year if month < 12 else year + 1),
            tzinfo=header.client.timezone
        )
        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        }

    def get_date_formsets(self, request):
        return [
            (
                None,
                {
                    'fields': (
                        'month',
                        'year'
                    )
                }
            )
        ]

    def kwargs_formsets(self):
        return [
            (
                None,
                {
                    'fields': (
                        'pecim',
                        'cadmm',
                        'enable_cac',
                        'cac_total'
                    )
                }
            )
        ]

    preview_list_fields = [
        'p_start_date',
        'p_end_date',
        'p_energy',
        'p_total',
    ]

    def p_start_date(self, data):
        return data.get('invoice', {}).get('start_date', '')

    p_start_date.name = "Start date"

    def p_end_date(self, data):
        return data.get('invoice', {}).get('end_date', '')

    p_end_date.name = "End date"

    def p_energy(self, data):
        return '%.2f' % (data.get('invoice', {}).get('energy', 0))

    p_energy.name = "Energy"

    def p_total(self, data):
        return '%s %.2f' % (
            data.get('invoice', {}).get('c_symbol', ''),
            data.get('invoice', {}).get('total', 0),
        )

    p_total.name = "Total"

    def __call__(self, customer, **kwargs):
        invoices = {}
        customer_header = kwargs['header']
        # g_start_date = kwargs['start_date']
        # g_end_date = kwargs['end_date']
        rental_data = kwargs['rental_data']
        maker_kwargs = kwargs['maker_kwargs']
        pecim = maker_kwargs['pecim']
        cadmm = maker_kwargs['cadmm']
        cac_total = maker_kwargs['cac_total']
        enable_cac = maker_kwargs['enable_cac']
        preview = kwargs.get('preview', False)
        for rental_id, measures_data in rental_data:
            rental = apps.get_model(
                'general.Rental'
            ).objects.select_related('local').get(pk=rental_id)
            for measure_id, g_result in measures_data:
                if not g_result.get('ok', False):
                    continue
                result = g_result['data']
                invoice_id = str(uuid4())
                if not preview:
                    invoice_id = customer_header.next_invoice_id
                c_maker_kwargs = customer_header.invoicemaker_kwargs
                header = c_maker_kwargs.get('header', {})
                inv_d = c_maker_kwargs.get('invoice', {})
                start_date = result.get('start_date')
                end_date = result.get('end_date')
                days = None
                if start_date and end_date:
                    start_date = datetime.fromisoformat(start_date)
                    end_date = datetime.fromisoformat(end_date)
                    end_date_f = end_date + timedelta(days=1)
                    days_diff = (end_date - start_date)
                    days = days_diff.days + (
                        1 if days_diff.seconds else 0
                    )
                    invoice_current = pecim * result.get('result')
                    invoice_cadmm_total = (invoice_current * cadmm) / 100
                    current_subtotal = invoice_current + invoice_cadmm_total
                    cac = 0
                    interest = 0
                    current_total = current_subtotal + interest
                    prev_total = 0
                    subtotal = current_total + prev_total
                    itbms = customer_header.invoicetax
                    if itbms is None:
                        itbms = 0
                    itbms_total = (subtotal * itbms) / 100
                    total = subtotal + itbms_total
                    g_total = total + (cac if enable_cac else 0)
                    meter = rental.local.extra.get('meter')
                    if not meter:
                        meter = result.get('meter', '')
                    balance_due = result.get('balance_due', {})
                    cac_p = result.get('cac_p', 0)
                    invoices[invoice_id] = {
                        'version': self.version,
                        'maker_id': self.id,
                        'maker_name': self.name,
                        'header': {
                            'title': header.get(
                                'title', 'Detalles de facturación'
                            ),
                            'logo_url': header.get(
                                'logo_url',
                                'https://apps.eneriongroup.com/icons/bussines.png'  # noqa: E501
                            ),
                            'name': customer_header.name,
                            'address': customer_header.addess,
                            'ruc': customer_header.legal_id,
                            'dv': header.get('dv', '')
                        },
                        'footer': {
                            'column': c_maker_kwargs.get(
                                'footer', {}
                            ).get('column', [])
                        },
                        'customer': {
                            'name': customer.name,
                            'address': customer.addess,
                            'ruc': customer.legal_id,
                            'dv': '-',
                            'tower': rental.local.extra.get('tower', ''),
                            'floor': rental.local.extra.get('floor', ''),
                            'meter': meter,
                        },
                        'invoice': {
                            'unique_id': invoice_id,
                            'date': end_date_f.strftime('%Y-%m-%d'),
                            # 'expiration': (datetime(
                            #     day=1,
                            #     month=(
                            #         end_date_f.month + 1
                            #         if end_date_f.month < 12 else
                            #         1
                            #     ),
                            #     year=(
                            #         end_date_f.year
                            #         if end_date_f.month < 12 else
                            #         end_date_f.year + 1
                            #     ),
                            #     tzinfo=customer_header.client.timezone
                            # ) - timedelta(days=1)).strftime('%Y-%m-%d'),
                            'expiration': (
                                end_date_f + timedelta(days=10)
                            ).strftime('%Y-%m-%d'),
                            'registry_type': inv_d.get(
                                'registry_type', 'Real'
                            ),
                            'month': start_date.strftime('%m'),
                            'year': start_date.strftime('%Y'),
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': end_date.strftime('%Y-%m-%d'),
                            'days': days,
                            'start_value': result.get('start_value'),
                            'end_value': result.get('end_value'),
                            'energy': result.get('result'),
                            'demand': result.get('demand'),
                            'pecim': pecim,
                            'cadmm': cadmm,
                            'cac': cac,
                            'current': invoice_current,
                            'cadmm_total': invoice_cadmm_total,
                            'current_subtotal': current_subtotal,
                            'interest': interest,
                            'current_total': current_total,
                            'prev_total': prev_total,
                            'subtotal': subtotal,
                            'itbms': itbms,
                            'itbms_total': itbms_total,
                            'total': total,
                            'g_total': g_total,
                            'c_symbol': (
                                customer_header.client.currency_model.synbol
                            ),
                            'enable_cac': enable_cac,
                            'cac_p': cac_p,
                            'common_area': ((cac_p * cac_total) / 100) * pecim,
                        },
                        'history': result.get('history'),
                        'balance_due': {
                            '0_30': balance_due.get('0_30', 0),
                            '30_60': balance_due.get('30_60', 0),
                            '60_90': balance_due.get('60_90', 0),
                            '90': balance_due.get('90', 0),
                        }
                    }
        ret = invoices
        if not preview:
            ret2 = {}
            for invoice_id, invoice_data in invoices.items():
                ret2[invoice_id] = self.invoice_create(
                    data=invoice_data,
                    invoice_id=invoice_id,
                    customer=customer
                )
                if 'history' in result and 'measure_id' in result:
                    measure = apps.get_model('x6gateapi.Measure').objects.get(
                        pk=result['measure_id']
                    )
                    if 'history' not in measure.extra_data:
                        measure.extra_data['history'] = {}
                    for history_item in result['history']:
                        measure.extra_data['history'][
                            history_item['date']
                        ] = history_item['value']
                    measure.save(
                        force_update=True, update_fields=['extra_data']
                    )
            return ret2
        return ret

    def post_measure_check_step(self, measures):
        sum_measures = 0
        for customer_id, rental_data in measures:
            for rental_id, measures_data in rental_data:
                for measure_id, result in measures_data:
                    data = result['data']
                    sum_measures += data['result']
        for customer_id, rental_data in measures:
            for rental_id, measures_data in rental_data:
                for measure_id, result in measures_data:
                    data = result['data']
                    data['cac_p'] = (data['result'] * 100) / sum_measures

    def make_invoice_file_name(self, invoice, n_id):
        i_data = invoice.data
        return slugify('invoice-%s-%s-%s-%s-%s' % (
            n_id,
            i_data.get('customer', {}).get('name', 'customer_name'),
            i_data.get('customer', {}).get('meter', 'customer_meter'),
            i_data.get('invoice', {}).get('month', 'month'),
            i_data.get('invoice', {}).get('year', 'year')
        ))


_HANDLERS = [
    PlazaRealInvoiceMaker(),
    BusinessParkInvoiceMaker()
]


class InvoiceMakers:

    @classmethod
    def choices(cls, allowed=None, add_none=True):
        choices = []
        if add_none:
            choices.append((None, '-----'))
        for handler in _HANDLERS:
            if hasattr(handler, 'name') and hasattr(handler, 'id'):
                if allowed is not None and handler.id not in allowed:
                    continue
                choices.append(
                    (getattr(handler, 'id'), getattr(handler, 'name'))
                )
        return choices

    @classmethod
    def get(cls, h_id):
        for handler in _HANDLERS:
            if getattr(handler, 'id') == h_id:
                return handler
        raise NotImplementedError(
            'Invoice maker id "%s" not implemented' % h_id
        )

    default = _HANDLERS[0].name

from celery import signature
from celery.result import AsyncResult
from datetime import datetime
from django import forms
from django.apps import apps
from django.db.models import Q
from django.contrib.admin import helpers
from django.contrib.admin.widgets import (
    FilteredSelectMultiple, AdminDateWidget
)
from django.core.exceptions import ValidationError
from django.http.response import HttpResponseBadRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.contrib import messages


class MainForm(forms.Form):

    start_date = forms.DateTimeField(
        widget=AdminDateWidget(),
        required=True
    )

    end_date = forms.DateTimeField(
        widget=AdminDateWidget(),
        required=True
    )

    def __init__(self, *args, **kwargs):
        customer_queryset = kwargs.pop('customer_queryset', None)
        super().__init__(*args, **kwargs)
        self.fields['customers'] = forms.ModelMultipleChoiceField(
            queryset=customer_queryset,
            widget=FilteredSelectMultiple('Customers', False),
            required=True,
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        is_dates = not (start_date is None or end_date is None)
        if is_dates and start_date >= end_date:
            raise ValidationError(
                'The start date must not be greater than the end date '
            )
        return cleaned_data


class InvoiceMaker():

    title = 'Generación de factura'

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
        return self.request.session.get('invoice_maker_data', {})

    @session_data.setter
    def session_data(self, value):
        self.request.session['invoice_maker_data'] = value

    @property
    def customer_queryset(self):
        queryset = apps.get_model('general.customer').objects.all().filter(
            removed_at__isnull=True
        )
        if not self.request.user.is_superuser:
            queryset = queryset.filter(
                client=self.request.user.megeuser.client
            )
        return queryset

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
        url = reverse('admin:invoice-maker')
        return HttpResponseRedirect(
            url if step is None else '%s?step=%s' % (
                reverse('admin:invoice-maker'),
                step
            )
        )

    def main_step(self):
        session_data = self.session_data
        main_data = session_data.get('main', {})
        form = None
        customer_queryset = self.customer_queryset.filter(
            is_invoice_header=False
        ).order_by('name')
        form_kwargs = {
            'customer_queryset': customer_queryset,
            'initial': main_data
        }
        formsets = [
            (
                None,
                {
                    'fields': (
                        'start_date',
                        'end_date',
                        'customers'
                    )
                }
            )
        ]
        if self.request.method == 'POST':
            form = MainForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                start_date = form.cleaned_data['start_date'].isoformat()
                main_data['start_date'] = start_date
                end_date = form.cleaned_data['end_date'].isoformat()
                main_data['end_date'] = end_date
                customers = form.cleaned_data['customers']
                customers_ids = list(customers.values_list('id', flat=True))
                main_data['customers'] = customers_ids
                session_data.update({'main': main_data})
                self.session_data = session_data
                return self.make_redirect('measure_check')
        else:
            form = MainForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Selection of dates and customers',
        }
        return TemplateResponse(
            self.request,
            'megedc/billing/invoice_make_main.html',
            self._make_conext(context)
        )

    def _measure_check_customer_proc(self, customer, start_date, end_date):
        all_data_ret = []
        rentals = customer.rentals.filter(
            (
                (
                    Q(end_at__isnull=True) & Q(start_at__lt=end_date)
                )
                | Q(end_at__gt=start_date)
            ),
            removed_at__isnull=True
        )

        for rental in rentals:
            if rental.local.removed_at is not None:
                continue
            rental_data = {
                'rental': rental,
                'local': rental.local,
                'measures': [],
                'total': 0.0
            }
            measures = rental.local.measures.filter(removed_at__isnull=True)
            for measure in measures:
                result = measure.calculate(
                    start_date=start_date,
                    end_date=end_date
                )
                amount = result.get('amount', 0.0)
                rental_data['total'] += amount
                rental_data['measures'].append({
                    'measure': measure,
                    'result_data': result,
                    'result': result.get('result', 0.0),
                    'amount': amount,
                    'amount_unit': measure.unit_cost.unit,
                    'desc': measure.make_invoice_item_desc(result)
                })
            all_data_ret.append(rental_data)
        return all_data_ret

    def measure_check_step(self):
        session_data = self.session_data
        main_data = session_data.get('main', {})
        start_date = None
        end_date = None
        customers = None

        if 'start_date' in main_data:
            start_date = datetime.fromisoformat(main_data['start_date'])

        if 'end_date' in main_data:
            end_date = datetime.fromisoformat(main_data['end_date'])

        if 'customers' in main_data:
            customers = self.customer_queryset.filter(
                pk__in=main_data['customers']
            ).order_by('name')

        measure_data = session_data.get('measure', [])

        if self.request.method == 'POST' and measure_data:
            return self.make_redirect('header_select')

        if measure_data:
            for consumer_data in measure_data:
                customer = self.customer_queryset.get(
                    pk=consumer_data['customer_id']
                )
                for rental_data in consumer_data['rentals']:
                    rental = customer.rentals.get(pk=rental_data['rental_id'])
                    for data in rental_data['measures']:
                        measure = rental.local.measures.get(
                            pk=data['measure_id']
                        )
                        data['measure'] = measure
                    rental_data['rental'] = rental
                    rental_data['local'] = rental.local
                consumer_data['customer'] = customer

        actual_ids = []
        for customer in customers:
            found = False
            for data in measure_data:
                if customer == data['customer']:
                    found = True
                    break
            actual_ids.append(customer.id)
            if not found:
                rentals = []
                try:
                    rentals = self._measure_check_customer_proc(
                        customer, start_date, end_date
                    )
                except Exception as exce:
                    self.admin.message_user(
                        self.request,
                        'Error: %s' % str(exce),
                        level=messages.WARNING
                    )
                    return self.make_redirect()
                consumer_data = {
                    'customer': customer,
                    'rentals': rentals
                }
                sub_total = 0.0
                for rental in consumer_data['rentals']:
                    sub_total += rental['total']
                tax = (sub_total * customer.invoicetax) / 100
                consumer_data['tax'] = tax
                consumer_data['sub_total'] = sub_total
                consumer_data['total'] = sub_total + tax
                consumer_data['symbol'] = customer.client.currency_model.synbol
                consumer_data['symbol_n'] = customer.client.currency_model.name
                measure_data.append(consumer_data)

        sesion_data = []
        for consumer_data in measure_data:
            if consumer_data['customer'].id not in actual_ids:
                continue
            s_consumer_data = {
                'customer_id': consumer_data['customer'].id,
                'tax': consumer_data['tax'],
                'sub_total': consumer_data['sub_total'],
                'total': consumer_data['total'],
                'symbol': consumer_data['symbol'],
                'symbol_n': consumer_data['symbol_n'],
                'rentals': []
            }
            for rental_data in consumer_data['rentals']:
                s_rental_data = {
                    'rental_id': rental_data['rental'].id,
                    'total': rental_data['total'],
                    'measures': []
                }
                for data in rental_data['measures']:
                    s_measure_data = {
                        'measure_id': data['measure'].id,
                        'result_data': data['result_data'],
                        'result': data['result'],
                        'amount': data['amount'],
                        'amount_unit': data['amount_unit'],
                        'desc': data['desc'],
                    }
                    s_rental_data['measures'].append(s_measure_data)
                s_consumer_data['rentals'].append(s_rental_data)
            sesion_data.append(s_consumer_data)
        session_data['measure'] = sesion_data
        self.session_data = session_data

        media = self.admin.media + forms.Media(js=[
            'admin/js/%s' % url for url in [
                'collapse.js'
            ]
        ])
        context = {
            'subtitle': 'Verification of items and totals',
            'data': measure_data,
            'media': media,
            'actual_ids': actual_ids
        }

        return TemplateResponse(
            self.request,
            'megedc/billing/invoice_maker_measure_select.html',
            self._make_conext(context)
        )

    def header_select_step(self):
        session_data = self.session_data

        if self.request.method == 'POST':
            header_id = self.request.POST.get('header_id')
            exists = self.customer_queryset.filter(pk=header_id).exists()
            if header_id and exists:
                session_data['header_id'] = header_id
                self.session_data = session_data
                return self.make_redirect('invoice_maker')
        header_id = session_data.get('header_id')
        if header_id:
            header_id = int(header_id)
        headers = self.customer_queryset.filter(
            is_invoice_header=True,
        )
        media = self.admin.media
        context = {
            'subtitle': 'Header selection',
            'headers': headers,
            'media': media,
            'header_id': header_id
        }

        return TemplateResponse(
            self.request,
            'megedc/billing/invoice_maker_headers.html',
            self._make_conext(context)
        )

    def invoice_maker_step(self):
        session_data = self.session_data
        measure_data = session_data.get('measure', [])
        main_data = session_data.get('main', {})
        header_id = session_data.get('header_id', {})
        download_all = None
        all_ready = True
        invoices_ids = []
        # start_date = None
        # end_date = None
        customers = None

        if self.request.method == 'POST' and self.request.POST.get('FINISH'):
            self.session_data = {}
            return self.make_redirect()

        # if 'start_date' in main_data:
        #     start_date = datetime.fromisoformat(main_data['start_date'])

        # if 'end_date' in main_data:
        #     end_date = datetime.fromisoformat(main_data['end_date'])

        if 'customers' in main_data:
            customers = self.customer_queryset.filter(
                pk__in=main_data['customers']
            ).order_by('name')

        header = self.customer_queryset.get(pk=header_id)

        invoices_data = session_data.get('invoices', {})

        for customer in customers:
            if str(customer.id) not in invoices_data:
                for m_data in measure_data:
                    if m_data['customer_id'] == customer.id:
                        data = m_data
                invoice = self.make_invoice(data, header)
                invoices_data[str(customer.id)] = {
                    'invoice_id': invoice.id,
                    'invoice': invoice
                }
        invoice_manager = self.invoice_manager
        for customer_id in invoices_data.keys():
            if 'invoice' not in invoices_data[customer_id]:
                invoices_data[customer_id]['invoice'] = invoice_manager.get(
                    pk=invoices_data[customer_id]['invoice_id']
                )
            if 'tasks_id' not in invoices_data[customer_id]:
                celery_task = signature(
                    'megedc.billing.tasks.make_invoice_file',
                    args=[invoices_data[customer_id]['invoice'].id]
                )
                task = celery_task.delay()
                invoices_data[customer_id]['tasks_id'] = task.id
            c_result = AsyncResult(invoices_data[customer_id]['tasks_id'])
            if c_result.status != 'SUCCESS' and all_ready:
                all_ready = False
            invoices_data[customer_id]['tasks_status'] = c_result.status

        for_session = {}
        for customer_id in invoices_data.keys():
            invoice_data = invoices_data[customer_id]
            invoices_ids.append(str(invoice_data['invoice_id']))
            for_session[customer_id] = {
                'invoice_id': invoice_data['invoice_id'],
                'tasks_id': invoice_data['tasks_id']
            }

        session_data.update({'invoices': for_session})
        self.session_data = session_data

        if all_ready:
            download_all = '%s?id=%s' % (
                reverse('admin:invoice-files-download'),
                ','.join(invoices_ids)
            )

        media = self.admin.media
        context = {
            'subtitle': 'Invoice creation',
            'invoices_data': invoices_data,
            'media': media,
            'download_all': download_all,
        }

        return TemplateResponse(
            self.request,
            'megedc/billing/invoice_maker_result.html',
            self._make_conext(context)
        )

    @property
    def invoice_manager(self):
        return apps.get_model('billing.invoice').objects

    def make_invoice(self, data, header):
        customer = self.customer_queryset.get(
            pk=data['customer_id']
        )
        return customer.make_invoice(header, data)

from celery import signature
from celery.result import AsyncResult
from datetime import datetime
from django import forms
from django_jsonform.widgets import JSONFormWidget
from django.apps import apps
from django.contrib.admin import helpers, widgets
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import response, JsonResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from megedc.billing.measue_calculators import Calculators


class MainForm(forms.Form):

    def __init__(self, *args, **kwargs):
        customer_queryset = kwargs.pop('customer_queryset', None)
        super().__init__(*args, **kwargs)
        self.fields['header'] = forms.ModelChoiceField(
            queryset=customer_queryset,
            required=True,
        )


class CustomerSelectForm(forms.Form):

    def __init__(self, *args, **kwargs):
        customer_queryset = kwargs.pop('customer_queryset', None)
        super().__init__(*args, **kwargs)
        self.fields['customers'] = forms.ModelMultipleChoiceField(
            queryset=customer_queryset,
            widget=widgets.FilteredSelectMultiple('Customers', False),
            required=True,
        )


class MeasureSelectForm(forms.Form):

    def __init__(self, *args, **kwargs):
        data = kwargs.pop('data', [])
        super().__init__(*args, **kwargs)
        for customer, rental_data in data:
            for rental, measures_data in rental_data:
                for measure, result in measures_data:
                    if result['ok']:
                        filed_name = result['filed_name']
                        filed_name_ow = result['filed_name_ow']
                        self.fields[filed_name] = forms.BooleanField(
                            required=False, initial=False,
                            widget=forms.CheckboxInput(attrs={
                                'for_accept': 'true'
                            })
                        )
                        calculator = Calculators.get(result['calculator'])
                        self.fields[filed_name_ow] = forms.JSONField(
                            initial=result['data'],
                            widget=JSONFormWidget(
                                calculator.measure_overwrite_scheme
                            )
                        )


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
        else:
            chgc_client = self.request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    client_id=chgc_client
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
            return response.HttpResponseBadRequest()
        step_handler_name = '%s_step' % step
        if hasattr(self, step_handler_name):
            return getattr(self, step_handler_name)()
        return response.HttpResponseBadRequest()

    def make_redirect(self, step=None):
        url = reverse('admin:invoice-maker')
        return response.HttpResponseRedirect(
            url if step is None else '%s?step=%s' % (
                reverse('admin:invoice-maker'),
                step
            )
        )

    def template_response(self, template, context):
        return TemplateResponse(
            self.request, template, self._make_conext(context)
        )

    def main_step(self):
        session_data = self.session_data
        main_data = session_data.get('main', {})
        form = None
        customer_queryset = self.customer_queryset.filter(
            is_invoice_header=True
        ).order_by('name')
        form_kwargs = {
            'initial': main_data,
            'customer_queryset': customer_queryset
        }
        formsets = [
            (
                None,
                {
                    'fields': [
                        'header'
                    ]
                }
            )
        ]
        if self.request.method == 'POST':
            form = MainForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                pass
                # start_date = form.cleaned_data['start_date'].isoformat()
                # main_data['start_date'] = start_date
                # end_date = form.cleaned_data['end_date'].isoformat()
                # main_data['end_date'] = end_date
                header = form.cleaned_data['header']
                main_data['header_id'] = header.id
                session_data.update({'main': main_data})
                self.session_data = session_data
                return self.make_redirect('dates')
        else:
            form = MainForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Selection of dates and header',
            'step': 'main'
        }
        return self.template_response(
            'megedc/billing/invoice_make_main.html', context
        )

    def dates_step(self):
        invoice_header = self.invoice_header
        if invoice_header is None:
            return self.make_redirect()
        session_data = self.session_data
        dates_data = session_data.get('dates', {})
        invoice_maker = invoice_header.invoicemaker
        form = None
        formsets = invoice_maker.get_date_formsets(self.request)
        form_kwargs = invoice_maker.get_date_form_kwargs(
            self.request, dates_data
        )
        if self.request.method == 'POST':
            form = invoice_maker.dates_from(self.request.POST, **form_kwargs)
            if form.is_valid():
                pass
                session_data.update({'dates': invoice_maker.get_dates(
                    self.request, form, header=invoice_header
                )})
                self.session_data = session_data
                return self.make_redirect('invoice_maker_kwargs')
        else:
            form = invoice_maker.dates_from(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Selection of dates and header',
            'step': 'dates',
            'perv': 'main',
        }
        return self.template_response(
            'megedc/billing/invoice_make_main.html', context
        )

    @property
    def invoice_header(self):
        obj_id = self.session_data.get('main', {}).get('header_id')
        if obj_id is None:
            return None
        try:
            return self.customer_queryset.get(pk=obj_id)
        except ObjectDoesNotExist:
            return None

    def invoice_maker_kwargs_step(self):
        invoice_header = self.invoice_header
        if invoice_header is None:
            return self.make_redirect()
        session_data = self.session_data
        header_kwargs_data = session_data.get('header_kwargs', {})
        invoice_maker = invoice_header.invoicemaker
        if invoice_maker.kwargs_form is None:
            return self.make_redirect('customers_select')
        form_kwargs = invoice_maker.kwargs_form_kwargs()
        form_kwargs.update({'initial': header_kwargs_data})
        formsets = invoice_maker.kwargs_formsets()
        if self.request.method == 'POST':
            form = invoice_maker.kwargs_form(self.request.POST, **form_kwargs)
            if form.is_valid():
                header_kwargs_data.update(
                    invoice_maker.kwargs_form_process(form)
                )
                session_data.update({'header_kwargs': header_kwargs_data})
                self.session_data = session_data
                return self.make_redirect('customers_select')
        else:
            form = invoice_maker.kwargs_form(**form_kwargs)
        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Invoice parameters',
            'perv': 'main',
            'step': 'invoice_maker_kwargs'
        }
        return self.template_response(
            'megedc/billing/invoice_make_main.html', context
        )

    def customers_select_step(self):
        session_data = self.session_data
        customer_select_data = session_data.get('customer_select', {})
        form = None
        customer_queryset = self.customer_queryset.filter(
            is_invoice_header=False
        ).order_by('name')
        form_kwargs = {
            'initial': customer_select_data,
            'customer_queryset': customer_queryset
        }
        formsets = [
            (
                None,
                {
                    'fields': (
                        'customers',
                    )
                }
            )
        ]
        if self.request.method == 'POST':
            form = CustomerSelectForm(self.request.POST, **form_kwargs)
            if form.is_valid():
                customers = form.cleaned_data['customers']
                customers_ids = list(customers.values_list('id', flat=True))
                customer_select_data['customers'] = customers_ids
                session_data.update({'customer_select': customer_select_data})
                self.session_data = session_data
                return self.make_redirect('measure_check')
        else:
            form = CustomerSelectForm(**form_kwargs)

        adminform = helpers.AdminForm(form, formsets, {})
        media = self.admin.media + adminform.media
        context = {
            'adminform': adminform,
            'media': media,
            'form_url': '',
            'errors': form.non_field_errors(),
            'subtitle': 'Selection of customers',
            'perv': (
                'main'
                if self.invoice_header.invoicemaker is None else
                'invoice_maker_kwargs'
            ),
            'step': 'customers_select'
        }
        return self.template_response(
            'megedc/billing/invoice_make_main.html', context
        )

    def measure_check_step(self):
        invoice_header = self.invoice_header
        session_data = self.session_data
        dates_data = session_data.get('dates', {})
        to_main = (
            invoice_header is None
            or 'start_date' not in dates_data
            or 'end_date' not in dates_data
        )
        if to_main:
            return self.make_redirect()
        customer_select_data = session_data.get('customer_select', {})
        if not customer_select_data.get('customers'):
            return self.make_redirect('customers_select')

        customer_measures = session_data.get('customer_measures', [])

        if self.request.method == 'POST':
            form = MeasureSelectForm(self.request.POST, data=customer_measures)
            if not customer_measures:
                return self.make_redirect('measure_check')
            # for customer_id, rental_data in customer_measures:
            #     for rental_id, measures_data in rental_data:
            #         for measure_id, result in measures_data:
            #             filed_name = result['filed_name']
            #             form.fields[filed_name] = forms.BooleanField(
            #                 required=False
            #             )
            if form.is_valid():
                new_customer_measures = []
                for customer_id, rental_data in customer_measures:
                    new_rental_data = []
                    for rental_id, measures_data in rental_data:
                        new_measures_data = []
                        for measure_id, result in measures_data:
                            filed_name = result['filed_name']
                            filed_name_ow = result['filed_name_ow']
                            if form.cleaned_data.get(filed_name):
                                result['data'] = form.cleaned_data[
                                    filed_name_ow
                                ]
                                new_measures_data.append((
                                    measure_id,
                                    result
                                ))
                        if new_measures_data:
                            new_rental_data.append(
                                (rental_id, new_measures_data)
                            )
                    if new_rental_data:
                        new_customer_measures.append(
                            (customer_id, new_rental_data)
                        )
                session_data.update({
                    'customer_measures_accepted': new_customer_measures
                })
                invoice_maker = invoice_header.invoicemaker
                if hasattr(invoice_maker, 'post_measure_check_step'):
                    invoice_maker.post_measure_check_step(
                        new_customer_measures
                    )
                self.session_data = session_data
                return self.make_redirect('invoice_check')
            else:
                return self.make_redirect('measure_check')
        measure_data = []
        customers = self.customer_queryset.filter(
            pk__in=customer_select_data.get('customers')
        ).order_by('name')
        start_date = datetime.fromisoformat(dates_data['start_date'])
        end_date = datetime.fromisoformat(dates_data['end_date'])
        s_customer = []
        for customer in customers:
            rental_data = self._make_customer_rentals(
                customer,
                start_date,
                end_date
            )
            s_rental_data = []
            for rental, measures_data in rental_data:
                s_measures_data = []
                for measure, result in measures_data:
                    filed_name = '%s_%s_%s' % (
                        customer.id, rental.id, measure.id
                    )
                    result['filed_name'] = filed_name
                    result['filed_name_ow'] = filed_name + '_ow'
                    result['accept'] = False
                    s_measures_data.append((measure.id, result))
                    # form.fields[filed_name] = forms.BooleanField(
                    #     required=False, initial=False
                    # )
                s_rental_data.append((rental.id, s_measures_data))
            s_customer.append((customer.id, s_rental_data))
            measure_data.append((customer, rental_data))
        session_data.update({'customer_measures': s_customer})
        self.session_data = session_data
        form = MeasureSelectForm(data=measure_data)
        adminform = helpers.AdminForm(form, [], {})
        media = self.admin.media + adminform.media + forms.Media(js=[
            'admin/js/%s' % url for url in [
                'collapse.js'
            ]
        ])
        context = {
            'media': media,
            'subtitle': 'Measures',
            'perv': 'customers_select',
            'step': 'measure_check',
            'data': measure_data,
            'form': form
        }
        return self.template_response(
            'megedc/billing/invoice_maker_measure_select2.html', context
        )

    def _make_customer_rentals(self, customer, start_date, end_date):
        ret = []
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
            measures = rental.local.measures.filter(removed_at__isnull=True)
            measures_data = []
            for measure in measures:
                result = None
                try:
                    data = measure.calculate(
                        start_date=start_date,
                        end_date=end_date,
                        header=self.invoice_header
                    )
                    calculator = Calculators.get(measure.calculator)
                    table_view = {
                        'headers': [
                            getattr(calculator, x).name
                            for x in calculator.table_view_fields
                        ],
                        'data': [
                            getattr(calculator, x)(data)
                            for x in calculator.table_view_fields
                        ],
                    }
                    result = {
                        'ok': True,
                        'data': data,
                        'table_view': table_view,
                        'calculator': measure.calculator
                    }
                except Exception as exc:
                    result = {
                        'ok': False,
                        'error': str(exc)
                    }
                measures_data.append((measure, result))
            ret.append((rental, measures_data))
        return ret

    def invoice_check_step(self):
        invoice_header = self.invoice_header
        session_data = self.session_data
        dates_data = session_data.get('dates', {})
        customer_measures = session_data.get('customer_measures_accepted', {})
        if not customer_measures:
            return self.make_redirect()
        start_date = datetime.fromisoformat(dates_data['start_date'])
        end_date = datetime.fromisoformat(dates_data['end_date'])
        data = []
        if self.request.method == 'POST':
            form = forms.Form(self.request.POST)
            if form.is_valid():
                final_invoices = []
                for customer_id, rental_data in customer_measures:
                    customer = self.customer_queryset.get(pk=customer_id)
                    invoices = customer.make_invoice(
                        header=invoice_header,
                        start_date=start_date,
                        end_date=end_date,
                        rental_data=rental_data,
                        maker_kwargs=session_data.get('header_kwargs', {}),
                        preview=False
                    )
                    d_invoices = []
                    for invoice_id, invoice in invoices.items():
                        celery_task = signature(
                            'megedc.billing.tasks.make_invoice_file',
                            args=[invoice.id]
                        )
                        task = celery_task.delay()
                        d_invoices.append((invoice.id, task.id))
                    final_invoices.append((customer_id, d_invoices))
                session_data.update({'final_invoices': final_invoices})
                self.session_data = session_data
                return self.make_redirect('end_step')
        form = forms.Form()
        for customer_id, rental_data in customer_measures:
            customer = self.customer_queryset.get(pk=customer_id)
            invoices = customer.make_invoice(
                header=invoice_header,
                start_date=start_date,
                end_date=end_date,
                rental_data=rental_data,
                maker_kwargs=session_data.get('header_kwargs', {}),
                preview=True
            )
            maker = customer.invoicemaker
            table_headers = [
                getattr(maker, x).name for x in maker.preview_list_fields
            ]
            invoices_data = []
            for invoice_id, invoice_data in invoices.items():
                cache.set(
                    'invoice_preview_%s' % (invoice_id),
                    invoice_data,
                    timeout=3600
                )
                row_data = [
                    getattr(maker, x)(invoice_data)
                    for x in maker.preview_list_fields
                ]
                invoices_data.append((invoice_id, row_data))
            data.append((customer, invoices_data, table_headers))
        media = self.admin.media
        context = {
            'media': media,
            'subtitle': 'Preview',
            'perv': 'measure_check',
            'step': 'invoice_check',
            'data': data,
            'form': form
        }
        return self.template_response(
            'megedc/billing/invoice_maker_preview_list.html', context
        )

    def end_step_step(self):
        session_data = self.session_data
        final_invoices = session_data.get('final_invoices', [])
        if not final_invoices:
            return self.make_redirect('invoice_check')

        if self.request.GET.get('retry') == 'true':
            q_customer_id = int(self.request.GET.get('customer_id'))
            q_invoice_id = int(self.request.GET.get('invoice_id'))
            if q_customer_id and q_invoice_id:
                new_data = []
                for customer_id, d_invoices in final_invoices:
                    if customer_id == q_customer_id:
                        new_data_f = []
                        for invoice_id, task_id in d_invoices:
                            if invoice_id == q_invoice_id:
                                celery_task = signature(
                                    'megedc.billing.tasks.make_invoice_file',
                                    args=[q_invoice_id]
                                )
                                task = celery_task.delay()
                                new_data_f.append((invoice_id, task.id))
                            else:
                                new_data_f.append((invoice_id, task_id))
                        new_data.append((customer_id, new_data_f))
                    else:
                        new_data.append((customer_id, d_invoices))
                session_data.update({'final_invoices': new_data})
                self.session_data = session_data
                return JsonResponse({})

        data = []
        for customer_id, d_invoices in final_invoices:
            customer = self.customer_queryset.get(pk=customer_id)
            invoices = []
            for invoice_id, task_id in d_invoices:
                invoice = customer.Invoices.get(pk=invoice_id)
                tasks = AsyncResult(task_id)
                invoices.append((invoice, tasks))
            data.append((customer, invoices))
        if self.request.GET.get('format') == 'json':
            s_data = []
            for customer, invoices in data:
                s_invoices = []
                for invoice, tasks in invoices:
                    s_invoices.append({
                        'id': str(invoice.id),
                        'task_status': str(tasks.status),
                        'url': str(self.request.build_absolute_uri(
                            reverse(
                                'admin:invoice-file-download',
                                args=[invoice.id]
                            )
                        ))
                    })
                s_data.append({
                    'id': str(customer.id),
                    'invoices': s_invoices
                })
            return JsonResponse(s_data, safe=False)
        media = self.admin.media
        context = {
            'media': media,
            'subtitle': 'Invoice list',
            'data': data,
            'step': 'end_step',
            'form': forms.Form()
        }
        return self.template_response(
            'megedc/billing/invoice_maker_list.html', context
        )

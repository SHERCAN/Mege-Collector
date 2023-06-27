from __future__ import absolute_import

import requests
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from megedc.billing.invoice_makers import InvoiceMakers


@shared_task
def make_invoice_file(invoice_id):
    invoice = apps.get_model('billing.invoice').objects.get(pk=invoice_id)
    invoice_maker = InvoiceMakers.get(invoice.data['maker_id'])
    url = invoice_maker.jasper_url()
    params = invoice_maker.jasper_params(invoice.id, False)
    headers = invoice_maker.jasper_headers()
    response = requests.get(
        url,
        auth=(settings.JASPERSERVER_USER, settings.JASPERSERVER_PASSWORD),
        params=params,
        headers=headers
    )
    response.raise_for_status()
    if invoice.file:
        invoice.file = None
        invoice.save()
        invoice.refresh_from_db()
    invoice.file_mime_type = response.headers['content-type']
    n_id = invoice.invoice_id if invoice.invoice_id else invoice_id
    name = 'invoice-%s.pdf' % n_id
    if hasattr(invoice_maker, 'make_invoice_file_name'):
        name = invoice_maker.make_invoice_file_name(invoice, n_id) + '.pdf'
    invoice.file.save(name, ContentFile(response.content))
    invoice.save()

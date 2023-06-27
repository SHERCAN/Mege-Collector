from django.db import models
from django.db.models.fields.files import FieldFile
from django.urls import reverse
from megedc.billing.invoice_id import Generators
from megedc.general.models import Customer
from os.path import join


def _invode_file_storage_path(instance, filename):
    return join(
        'invoices',
        str(instance.id % 4096),
        str(instance.id),
        filename
    )


class InvoiceFieldFile(FieldFile):

    # def __str__(self):
    #     if self.name:
    #         return basename(self.name) or ''
    #     return ''

    @property
    def url(self):
        self._require_file()
        return reverse('admin:invoice-file-download', args=(self.instance.pk,))


class InvoiceFileField(models.FileField):

    attr_class = InvoiceFieldFile


class Invoice(models.Model):

    data = models.JSONField(
        default=dict,
        blank=True,
        null=True
    )

    invoice_id = models.CharField(
        max_length=128,
        default=Generators.get(Generators.default_generator_id)
    )

    file = InvoiceFileField(
        upload_to=_invode_file_storage_path,
        null=True,
        blank=True
    )

    file_mime_type = models.CharField(
        max_length=256,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    removed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='Invoices',
    )

    def __str__(self):
        return '(%s) %s' % (self.customer.name, self.invoice_id)

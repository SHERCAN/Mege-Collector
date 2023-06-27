import requests
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.utils import unquote
from django.http.response import (
    FileResponse, HttpResponseNotFound, HttpResponseRedirect
)
from django.urls import path
from django.urls.base import reverse
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from megedc.billing.invoice_maker2 import InvoiceMaker
from os.path import join, basename
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
from megedc.billing.invoice_makers import InvoiceMakers
from megedc.general.admin import CustomerRelatedFieldListFilter


# Fot register Admin classes
_for_register = [
    # (model_name, Admin class)
]


class InvoiceAdmin(admin.ModelAdmin):

    fields = [
        'customer',
        'invoice_id',
        'download',
        'created_at',
    ]

    list_display = [
        'invoice_id',
        'customer',
        'download',
        'created_at',
    ]

    readonly_fields = [
        'download'
    ]

    ordering = [
        'id',
    ]

    search_fields = [
        'invoice_id',
        'customer__name',
    ]

    list_filter = [
        ('customer', CustomerRelatedFieldListFilter),
    ]

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url='',
                        extra_context=None):
        if object_id is None:
            return HttpResponseRedirect(
                reverse('admin:invoice-maker')
            )
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('customer')
        if not request.user.is_superuser:
            queryset = queryset.filter(
                customer__client=request.user.megeuser.client
            )
        else:
            chgc_client = request.session.get('chgc_client')
            if chgc_client:
                queryset = queryset.filter(
                    customer__client_id=chgc_client
                )
        return queryset.filter(removed_at__isnull=True).select_related(
            'customer'
        )

    def download(self, obj):
        if obj.file is not None:
            return mark_safe('<a href="%s">%s</a>' % (
                obj.file.url, obj.file.name.split('/')[-1]
            ))
        return ''

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                '<path:object_id>/download/',
                self.admin_site.admin_view(self.file_download_view),
                name="invoice-file-download"
            ),
            path(
                'download/',
                self.admin_site.admin_view(self.file_download_view),
                name="invoice-files-download"
            ),
            path(
                'maker/',
                self.admin_site.admin_view(self.invoice_maker_view),
                name="invoice-maker"
            ),
        ]
        return my_urls + urls

    def file_download_view(self, request, object_id=None):
        if request.GET.get('preview', False):
            data = cache.get('invoice_preview_%s' % (object_id), None)
            invoice_maker = InvoiceMakers.get(data['maker_id'])
            url = invoice_maker.jasper_url()
            params = invoice_maker.jasper_params(object_id, True)
            headers = invoice_maker.jasper_headers()
            response = requests.get(
                url,
                auth=(
                    settings.JASPERSERVER_USER,
                    settings.JASPERSERVER_PASSWORD
                ),
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return FileResponse(
                ContentFile(response.content),
                as_attachment=True,
                filename='%s.pdf' % (object_id),
                headers={
                    ''
                    'Content-Type': response.headers['content-type']
                }
            )
        invoice_ids = []
        if object_id is not None:
            invoice_ids.append(object_id)
        else:
            invoice_ids.extend(unquote(request.GET.get('id', '')).split(','))

        if invoice_ids:
            queryset = self.get_queryset(request)
            queryset = queryset.filter(
                pk__in=[unquote(x) for x in invoice_ids]
            )
            n_files = queryset.count()
            if n_files == 0:
                return HttpResponseNotFound()
            if n_files > 1:
                with TemporaryDirectory() as tmpdirname:
                    zippath = join(tmpdirname, 'invoices.zip')
                    zipfile = ZipFile(
                        zippath,
                        mode='w',
                        compression=ZIP_DEFLATED
                    )
                    for invoice in queryset:
                        zipfile.write(
                            invoice.file.path,
                            basename(invoice.file.path)
                        )
                    zipfile.close()
                    return FileResponse(
                        open(zippath, 'br'),
                        as_attachment=True,
                    )

            else:
                invoice = queryset.first()
                try:
                    return FileResponse(
                        invoice.file,
                        as_attachment=True,
                        headers={
                            'Content-Length': invoice.file.size,
                            'Content-Type': invoice.file_mime_type
                        }
                    )
                except FileNotFoundError:
                    return HttpResponseNotFound()
        return HttpResponseNotFound()

    def delete_model(self, request, obj):
        obj.removed_at = localtime()
        obj.save()

    def delete_queryset(self, request, queryset):
        queryset.update(removed_at=localtime())

    @csrf_protect_m
    def invoice_maker_view(self, request):
        maker = InvoiceMaker(self, request)
        return maker.response()


_for_register.append(('billing.invoice', InvoiceAdmin))


for model_name, admin_class in _for_register:
    model = apps.get_model(model_name)
    if not admin.site.is_registered(model):
        admin.site.register(model, admin_class)

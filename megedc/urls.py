from django.conf import settings
from django.contrib import admin
from django.urls import path
from .accuenergy import urls as accuenergy_url
from .x6gateapi import urls as x6api_url
from .data_export import urls as data_export_url
from .billing import urls as billing_url
from .views import VersionAPIView


urlpatterns = [
    path(settings.MEGEDC_URL_PATH + '/version', VersionAPIView.as_view()),
    path(settings.MEGEDC_URL_PATH + '/admin/', admin.site.urls),
    path(settings.MEGEDC_URL_PATH + '/x6gateapi/', x6api_url.urls),
    path(settings.MEGEDC_URL_PATH + '/accuenergy/', accuenergy_url.urls),
    path(settings.MEGEDC_URL_PATH + '/data_export/', data_export_url.urls),
    path(settings.MEGEDC_URL_PATH + '/billing/', billing_url.urls),
]

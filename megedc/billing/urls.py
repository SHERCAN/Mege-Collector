from django.urls import path
from megedc.billing import views


urls = (
    [
        path(
            'invoice-data',
            views.InvoiceDateRetriveAPIView.as_view(),
            name='get-invoice-data'
        ),
        path(
            'invoice-data/<str:pk>',
            views.InvoiceDateRetriveAPIView.as_view(),
            name='get-invoice-data2'
        ),
    ],
    'billing',
    'billing'
)

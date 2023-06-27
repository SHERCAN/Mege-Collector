from django.urls import path
from megedc.data_export import views


urls = (
    [
        path(
            'rt_data/',
            views.RTDataExportAPIView.as_view(),
            name='rtdata-export'
        ),
        path(
            'rt_alarm/',
            views.RTAlarmDataListAPIView.as_view(),
            name='rtalarm-export'
        ),
        path(
            'trendlogdata/',
            views.TrendLogDataListAPIView.as_view(),
            name='trendlogdata-export'
        ),
        path(
            'measure_calc/<int:pk>',
            views.MeasureCalcAPIView.as_view(),
            name='measure-calc-export'
        ),
    ],
    'data_export',
    'data_export'
)

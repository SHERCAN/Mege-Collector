from django.urls import path
from megedc.x6gateapi import views


urls = (
    [
        path(
            '<str:project_uuid>/gateway',
            views.GatewayCreateApiView.as_view(),
            name='gateway-create'
        ),
        path(
            '<str:project_uuid>/gateway/<str:sn>',
            views.GatewayRetrieveAPIView.as_view(),
            name='gateway-retrieve'
        ),
        path(
            '<str:project_uuid>/device/<str:sn>',
            views.DeviceListCreateApiView.as_view(),
            name='device-create'
        ),
        path(
            '<str:project_uuid>/realdata/<str:sn>',
            views.RTDataCreateApiView.as_view(),
            name='rtdata-create'
        ),
        path(
            '<str:project_uuid>/alarmdata/<str:sn>',
            views.RTAlarmCreateApiView.as_view(),
            name='alarmdata-create'
        ),
        # path(
        #     '<str:project_uuid>/calldata/<str:sn>',
        #     views.CallDataApiView.as_view()
        # ),
        path(
            '<str:project_uuid>/trendlogdata/<str:sn>',
            views.TrendLogDataCreateApiView.as_view(),
            name='trendlogdata-create'
        ),
    ],
    'x6gateapi',
    'x6gateapi'
)

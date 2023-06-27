from django.urls import path
from megedc.accuenergy import views


urls = (
    [
        path(
            '<str:project_uuid>/post_channel',
            views.AccuenergyPostChannel.as_view(),
            name='post-channel'
        ),
    ],
    'accuenergy',
    'accuenergy'
)

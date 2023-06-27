from django.contrib.admin.apps import AdminConfig


class MegeDCAdminConfig(AdminConfig):
    default_site = 'megedc.admin.MegeDCAdminSite'

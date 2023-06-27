from django.contrib import admin
from django.urls import path
from django.http.response import HttpResponseRedirect
from django import forms
from django.apps import apps


class ClientChangeForm(forms.Form):

    chgc_redirect = forms.CharField(widget=forms.widgets.HiddenInput())
    chgc_client = forms.CharField(
        required=False,
        widget=forms.widgets.Select()
    )


class MegeDCAdminSite(admin.AdminSite):

    site_title = 'MeGe Data Collector'
    site_header = 'MeGe Data Collector'
    index_title = ''
    site_url = False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                'client_select/',
                self.admin_view(self.client_select),
                name="client-select"
            ),
        ]
        return my_urls + urls

    def client_select(self, request):
        client_change_form = ClientChangeForm(request.POST)
        if client_change_form.is_valid():
            client = client_change_form.cleaned_data.get('chgc_client')
            redirect = client_change_form.cleaned_data['chgc_redirect']
            request.session['chgc_client'] = client
            return HttpResponseRedirect(redirect)
        return HttpResponseRedirect('https://www.ucab.edu.ve')

    def each_context(self, request):
        client_change_form = ClientChangeForm(
            initial={
                'chgc_redirect': request.get_full_path(),
                'chgc_client': request.session.get('chgc_client')
            }
        )
        manager = apps.get_model('general.client').objects
        values = [(None, 'all')] + list(
            manager.all().values_list('id', 'name').order_by('name')
        )
        client_change_form.fields['chgc_client'].widget.choices = values
        context = super().each_context(request)
        context['client_change_form'] = client_change_form
        return context
